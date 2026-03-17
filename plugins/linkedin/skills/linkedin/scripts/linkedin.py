#!/usr/bin/env python3
"""
LinkedIn Intelligence Wrapper

Query builder + result parser + Proxycurl integration for LinkedIn OSINT.

**Architecture:** This wrapper does NOT search the web itself.
The searching is done by the Claude agent (via WebSearch tool) during stalker runs.
This wrapper provides:
1. Optimized dork query generation
2. LinkedIn URL/snippet parsing to extract structured data
3. Proxycurl API integration (when PROXYCURL_API_KEY configured)

Usage in stalker context (Claude agent):
    import sys; sys.path.insert(0, 'tools/lib')
    from linkedin import build_queries, parse_search_results, parse_profile_url, proxycurl_lookup

    # Step 1: Generate dork queries for WebSearch
    queries = build_queries("Mario Rossi", company="Emisfera", location="Verbania")
    # → ['site:linkedin.com/in/ "Mario Rossi" "Emisfera" "Verbania"', ...]

    # Step 2: Agent runs WebSearch with those queries, gets results

    # Step 3: Parse results to extract structured data
    profiles = parse_search_results(websearch_results)
    # → [{"name": "Mario Rossi", "headline": "CTO at Emisfera", "url": "...", ...}]

    # Step 4: If Proxycurl available, get full profile
    full = proxycurl_lookup("https://www.linkedin.com/in/mario-rossi-123/")

CLI (for testing with Proxycurl):
    python3 linkedin.py --queries "Mario Rossi" --company "Emisfera"
    python3 linkedin.py --parse-url "https://www.linkedin.com/in/mario-rossi-123/"
    python3 linkedin.py --proxycurl "https://www.linkedin.com/in/mario-rossi-123/"

Required .env keys:
    (none for query building/parsing)
    PROXYCURL_API_KEY  — optional, for structured API lookups
"""

import os
import re
import json
import argparse
import html
from pathlib import Path
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv

BRAIN = Path(__file__).parent.parent.parent.resolve()
load_dotenv(str(BRAIN / '.env'))


# ============================================================
# QUERY BUILDERS — generate optimized dork strings
# ============================================================

def build_queries(
    name: str,
    company: Optional[str] = None,
    location: Optional[str] = None,
    role: Optional[str] = None,
    query_type: str = "person",
) -> List[str]:
    """Build optimized search queries for LinkedIn dorking.

    Returns multiple queries from specific to broad. The agent should
    try them in order, stopping when results are found.

    Args:
        name: Person or company name
        company: Company filter (person search)
        location: Location filter
        role: Job title filter (person search)
        query_type: "person", "company", or "employees"

    Returns:
        List of search query strings (most specific first)
    """
    queries = []

    if query_type == "person":
        # Most specific: site + name + all filters
        parts = [f'site:linkedin.com/in/ "{name}"']
        if company:
            parts.append(f'"{company}"')
        if location:
            parts.append(f'"{location}"')
        if role:
            parts.append(f'"{role}"')
        queries.append(" ".join(parts))

        # Medium: site + name + company only
        if company and (location or role):
            queries.append(f'site:linkedin.com/in/ "{name}" "{company}"')

        # Broader: site + name only
        if company or location or role:
            queries.append(f'site:linkedin.com/in/ "{name}"')

        # Broadest: no site restriction
        broad_parts = [f'linkedin.com "{name}"']
        if company:
            broad_parts.append(f'"{company}"')
        queries.append(" ".join(broad_parts))

    elif query_type == "company":
        queries.append(f'site:linkedin.com/company/ "{name}"')
        if location:
            queries.append(f'site:linkedin.com/company/ "{name}" "{location}"')
        queries.append(f'linkedin.com/company "{name}"')

    elif query_type == "employees":
        parts = [f'site:linkedin.com/in/ "{name}"']
        if role:
            parts.append(f'"{role}"')
        if location:
            parts.append(f'"{location}"')
        queries.append(" ".join(parts))

        # Also try "works at" pattern
        queries.append(f'site:linkedin.com/in/ "{name}" current')

    return queries


def build_employee_queries(
    company: str,
    roles: Optional[List[str]] = None,
    location: Optional[str] = None,
) -> List[str]:
    """Build queries to find employees of a company.

    Args:
        company: Company name
        roles: List of roles to search for (e.g. ["CEO", "CTO", "developer"])
        location: Location filter

    Returns:
        List of search queries
    """
    queries = []

    if roles:
        for role in roles:
            q = f'site:linkedin.com/in/ "{company}" "{role}"'
            if location:
                q += f' "{location}"'
            queries.append(q)
    else:
        q = f'site:linkedin.com/in/ "{company}"'
        if location:
            q += f' "{location}"'
        queries.append(q)

    return queries


# ============================================================
# PARSERS — extract structured data from search results
# ============================================================

def parse_search_results(results: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Parse WebSearch results into structured LinkedIn profiles.

    Args:
        results: List of search results, each with "title", "url", "snippet"

    Returns:
        List of parsed profile dicts
    """
    profiles = []

    for r in results:
        url = r.get("url", "")
        title = r.get("title", "")
        snippet = r.get("snippet", "")

        # Only process LinkedIn profile URLs
        if "linkedin.com/in/" not in url:
            continue

        profile = parse_linkedin_title(title)
        profile["url"] = url
        profile["slug"] = _extract_slug(url)

        # Extract additional data from snippet
        snippet_data = parse_linkedin_snippet(snippet)
        for key, val in snippet_data.items():
            if val and not profile.get(key):
                profile[key] = val

        profiles.append(profile)

    return profiles


def parse_linkedin_title(title: str) -> Dict[str, Any]:
    """Parse a LinkedIn page title into structured data.

    LinkedIn titles follow patterns like:
    - "Mario Rossi - CTO - Emisfera | LinkedIn"
    - "Mario Rossi | LinkedIn"
    - "Mario Rossi - CTO at Emisfera - Verbania | LinkedIn"

    Returns:
        Dict with name, headline, current_company (when extractable)
    """
    result = {"name": None, "headline": None, "current_company": None}

    # Remove LinkedIn suffix
    clean = re.sub(r'\s*\|?\s*LinkedIn\s*$', '', title).strip()
    clean = html.unescape(clean)

    if not clean:
        return result

    # Split by " - "
    parts = [p.strip() for p in clean.split(' - ') if p.strip()]

    if parts:
        result["name"] = parts[0]

    if len(parts) > 1:
        result["headline"] = " - ".join(parts[1:])

        # Try to extract company from headline
        headline = result["headline"]
        # "CTO at Emisfera" or "CTO presso Emisfera"
        at_match = re.search(r'(?:at|presso|@)\s+(.+?)(?:\s*-\s*|$)', headline)
        if at_match:
            result["current_company"] = at_match.group(1).strip()

    return result


def parse_linkedin_snippet(snippet: str) -> Dict[str, Any]:
    """Extract structured data from a LinkedIn search snippet.

    Snippets often contain location, connection count, experience info.
    """
    result = {
        "location": None,
        "summary": None,
        "connections": None,
        "experience_years": None,
    }

    if not snippet:
        return result

    snippet = html.unescape(snippet)
    result["summary"] = snippet[:300]  # Keep first 300 chars as summary

    # Location patterns
    loc_patterns = [
        r'(?:Location|Località|Luogo|Zona)[:·]\s*([^·\n|]+)',
        r'(?:^|\s)(\w+(?:\s\w+)?,\s*(?:Italy|Italia|Piemonte|Lombardia|Lazio|Veneto|Toscana|Emilia|Campania|Sicilia|Sardegna|Puglia|Calabria|Liguria|Friuli|Marche|Abruzzo|Molise|Umbria|Basilicata|Trentino|Valle))',
    ]
    for pattern in loc_patterns:
        match = re.search(pattern, snippet, re.IGNORECASE)
        if match:
            result["location"] = match.group(1).strip().rstrip('·').strip()
            break

    # Connections
    conn_match = re.search(r'(\d+)\+?\s*(?:connections|collegamenti|contatti)', snippet, re.IGNORECASE)
    if conn_match:
        result["connections"] = int(conn_match.group(1))

    # Experience years
    exp_match = re.search(r'(\d+)\+?\s*(?:years|anni)\s*(?:of\s*)?(?:experience|esperienza)', snippet, re.IGNORECASE)
    if exp_match:
        result["experience_years"] = int(exp_match.group(1))

    return result


def parse_profile_url(url: str) -> Dict[str, str]:
    """Extract metadata from a LinkedIn URL.

    Args:
        url: LinkedIn URL

    Returns:
        Dict with url_type ("profile", "company", "post", "other"),
        slug, and clean_url
    """
    result = {"url": url, "url_type": "other", "slug": None, "clean_url": url}

    if "/in/" in url:
        result["url_type"] = "profile"
        result["slug"] = _extract_slug(url)
        result["clean_url"] = f"https://www.linkedin.com/in/{result['slug']}/"
    elif "/company/" in url:
        result["url_type"] = "company"
        match = re.search(r'/company/([^/?#]+)', url)
        if match:
            result["slug"] = match.group(1)
            result["clean_url"] = f"https://www.linkedin.com/company/{result['slug']}/"
    elif "/posts/" in url or "/pulse/" in url:
        result["url_type"] = "post"

    return result


def parse_company_page(results: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Parse search results for company LinkedIn pages.

    Args:
        results: WebSearch results

    Returns:
        List of parsed company dicts
    """
    companies = []

    for r in results:
        url = r.get("url", "")
        if "linkedin.com/company/" not in url:
            continue

        title = r.get("title", "")
        snippet = r.get("snippet", "")

        company = {
            "url": url,
            "name": re.sub(r'\s*\|?\s*LinkedIn\s*$', '', title).strip(),
            "description": snippet[:300] if snippet else None,
        }

        # Extract employee count from snippet
        emp_match = re.search(r'(\d[\d,.]+)\s*(?:employees|dipendenti|followers|seguaci)', snippet, re.IGNORECASE)
        if emp_match:
            company["size_indicator"] = emp_match.group(0)

        companies.append(company)

    return companies


def _extract_slug(url: str) -> Optional[str]:
    """Extract profile slug from LinkedIn URL."""
    match = re.search(r'/in/([^/?#]+)', url)
    return match.group(1) if match else None


# ============================================================
# PROXYCURL — structured API lookups
# ============================================================

def proxycurl_available() -> bool:
    """Check if Proxycurl API is configured."""
    return bool(os.getenv('PROXYCURL_API_KEY'))


def proxycurl_lookup(linkedin_url: str) -> Optional[Dict[str, Any]]:
    """Lookup a LinkedIn profile via Proxycurl API.

    Requires PROXYCURL_API_KEY in .env. Costs 1 credit (~$0.01).

    Args:
        linkedin_url: Full LinkedIn profile URL

    Returns:
        Structured profile data, or None if not configured
    """
    api_key = os.getenv('PROXYCURL_API_KEY')
    if not api_key:
        return None

    import requests

    try:
        resp = requests.get(
            'https://nubela.co/proxycurl/api/v2/linkedin',
            params={'url': linkedin_url, 'use_cache': 'if-present'},
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=30,
        )

        if resp.status_code == 200:
            data = resp.json()
            return {
                "url": linkedin_url,
                "name": f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
                "headline": data.get('headline'),
                "location": data.get('city') or data.get('country_full_name'),
                "summary": data.get('summary'),
                "current_company": _extract_current_company_proxycurl(data),
                "experiences": data.get('experiences', []),
                "education": data.get('education', []),
                "skills": [s.get('name', s) if isinstance(s, dict) else s for s in data.get('skills', [])],
                "connections": data.get('connections'),
                "profile_pic_url": data.get('profile_pic_url'),
                "source": "proxycurl",
            }
        elif resp.status_code == 404:
            return {"url": linkedin_url, "error": "Profile not found", "source": "proxycurl"}
        elif resp.status_code == 403:
            return {"url": linkedin_url, "error": "Invalid API key", "source": "proxycurl"}
        elif resp.status_code == 429:
            return {"url": linkedin_url, "error": "Rate limited", "source": "proxycurl"}
        else:
            return {"url": linkedin_url, "error": f"HTTP {resp.status_code}", "source": "proxycurl"}

    except Exception as e:
        return {"url": linkedin_url, "error": str(e), "source": "proxycurl"}


def proxycurl_company(linkedin_url: str) -> Optional[Dict[str, Any]]:
    """Lookup a company via Proxycurl. Costs 1 credit."""
    api_key = os.getenv('PROXYCURL_API_KEY')
    if not api_key:
        return None

    import requests

    try:
        resp = requests.get(
            'https://nubela.co/proxycurl/api/linkedin/company',
            params={'url': linkedin_url, 'use_cache': 'if-present'},
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "url": linkedin_url,
                "name": data.get('name'),
                "description": data.get('description'),
                "website": data.get('website'),
                "industry": data.get('industry'),
                "company_size": data.get('company_size'),
                "headquarters": data.get('hq', {}).get('city') if data.get('hq') else None,
                "founded_year": data.get('founded_year'),
                "specialities": data.get('specialities', []),
                "follower_count": data.get('follower_count'),
                "source": "proxycurl",
            }
        return {"url": linkedin_url, "error": f"HTTP {resp.status_code}", "source": "proxycurl"}

    except Exception as e:
        return {"url": linkedin_url, "error": str(e), "source": "proxycurl"}


def proxycurl_search(
    name: Optional[str] = None,
    company: Optional[str] = None,
    role: Optional[str] = None,
    location: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Search for people via Proxycurl Person Search API.

    Costs 3 credits per search (~$0.03).

    Returns:
        List of {linkedin_profile_url, ...}, or None if not configured
    """
    api_key = os.getenv('PROXYCURL_API_KEY')
    if not api_key:
        return None

    import requests

    params = {}
    if name:
        parts = name.split(maxsplit=1)
        params['first_name'] = parts[0]
        if len(parts) > 1:
            params['last_name'] = parts[1]
    if company:
        params['current_company_name'] = company
    if role:
        params['current_role_title'] = role
    if location:
        params['city'] = location

    try:
        resp = requests.get(
            'https://nubela.co/proxycurl/api/search/person/',
            params=params,
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json().get('results', [])
        return None
    except Exception as e:
        print(f"Proxycurl search failed: {e}")
        return None


def _extract_current_company_proxycurl(data: dict) -> Optional[str]:
    """Extract current company from Proxycurl profile data."""
    experiences = data.get('experiences', [])
    for exp in experiences:
        if not exp.get('ends_at'):  # No end date = current
            return exp.get('company')
    return None


# ============================================================
# HIGH-LEVEL CONVENIENCE
# ============================================================

def stalker_linkedin_block(
    name: str,
    company: Optional[str] = None,
    location: Optional[str] = None,
    role: Optional[str] = None,
    level: int = 5,
) -> Dict[str, Any]:
    """Generate a complete LinkedIn investigation plan for stalker.

    Returns a dict with:
    - queries: list of search queries to run
    - proxycurl_available: bool
    - recommended_actions: list of steps

    The stalker agent uses this to know what to do.
    """
    result = {
        "queries": build_queries(name, company, location, role),
        "proxycurl_available": proxycurl_available(),
        "recommended_actions": [],
    }

    # Level 1-3: basic search
    result["recommended_actions"].append(
        f"WebSearch: {result['queries'][0]}"
    )

    # Level 4-6: employee search if company context
    if level >= 4 and company:
        emp_queries = build_employee_queries(company, roles=["CEO", "CTO", "founder"])
        result["employee_queries"] = emp_queries
        result["recommended_actions"].append(
            f"Search employees: {emp_queries[0]}"
        )

    # Level 7+: Proxycurl if available
    if level >= 7 and result["proxycurl_available"]:
        result["recommended_actions"].append(
            "Use proxycurl_lookup() on found profile URLs for full data"
        )

    return result


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="LinkedIn Intelligence Wrapper")
    parser.add_argument('--queries', type=str, help='Generate dork queries for a name')
    parser.add_argument('--company', type=str, help='Company filter')
    parser.add_argument('--location', type=str, help='Location filter')
    parser.add_argument('--role', type=str, help='Role filter')
    parser.add_argument('--parse-url', type=str, help='Parse a LinkedIn URL')
    parser.add_argument('--proxycurl', type=str, help='Proxycurl lookup by URL')
    parser.add_argument('--proxycurl-company', type=str, help='Proxycurl company lookup')
    parser.add_argument('--plan', type=str, help='Generate stalker plan for a name')
    parser.add_argument('--level', type=int, default=5, help='Stalker level (1-10)')
    args = parser.parse_args()

    if args.queries:
        queries = build_queries(
            args.queries,
            company=args.company,
            location=args.location,
            role=args.role,
        )
        print("Generated queries (most specific first):")
        for i, q in enumerate(queries, 1):
            print(f"  {i}. {q}")

    elif args.parse_url:
        result = parse_profile_url(args.parse_url)
        print(json.dumps(result, indent=2))

    elif args.proxycurl:
        result = proxycurl_lookup(args.proxycurl)
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("Proxycurl not configured (PROXYCURL_API_KEY missing in .env)")

    elif args.proxycurl_company:
        result = proxycurl_company(args.proxycurl_company)
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("Proxycurl not configured")

    elif args.plan:
        plan = stalker_linkedin_block(
            args.plan,
            company=args.company,
            location=args.location,
            role=args.role,
            level=args.level,
        )
        print(json.dumps(plan, indent=2, ensure_ascii=False))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
