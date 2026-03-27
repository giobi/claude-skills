#!/usr/bin/env python3
"""
Internet.bs API Library

Provides reusable functions for Internet.bs domain operations.
Used by agents and cron jobs.
"""

import os
import sys
import requests
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime


def _find_env_file() -> Optional[Path]:
    """Find .env file: relative to this file, then walk up from cwd"""
    # Relative to this file: tools/lib/ -> tools/ -> brain root
    relative = Path(__file__).parent.parent.parent / '.env'
    if relative.exists():
        return relative

    # Walk up from cwd
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        candidate = parent / '.env'
        if candidate.exists():
            return candidate

    return None


def _load_env(env_file: Optional[str] = None):
    """Load env vars from file. If not specified, auto-detect."""
    path = Path(env_file) if env_file else _find_env_file()
    if path and path.exists():
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    k = k.strip()
                    if k not in os.environ:  # don't override existing env vars
                        os.environ[k] = v.strip().strip('"').strip("'")


def _get_credentials(env_file: Optional[str] = None) -> tuple:
    """Get Internet.bs API credentials"""
    _load_env(env_file)
    api_key = os.getenv('INTERNETBS_API_KEY')
    password = os.getenv('INTERNETBS_PASSWORD')

    if not api_key or not password:
        raise ValueError("INTERNETBS_API_KEY and INTERNETBS_PASSWORD required in .env")

    return api_key, password


def _make_request(endpoint: str, params: Dict = None, env_file: Optional[str] = None) -> Dict:
    """
    Make API request to Internet.bs

    Args:
        endpoint: API endpoint (e.g., 'Domain/List')
        params: Additional query parameters

    Returns:
        Response data dict
    """
    api_key, password = _get_credentials(env_file)

    base_url = 'https://api.internet.bs'
    url = f"{base_url}/{endpoint}"

    # Add credentials to params
    request_params = {
        'ApiKey': api_key,
        'Password': password,
        'ResponseFormat': 'JSON'
    }

    if params:
        request_params.update(params)

    response = requests.get(url, params=request_params)

    if response.status_code != 200:
        print(f"❌ Internet.bs API error: {response.status_code}")
        print(response.text)
        return {}

    return response.json()


def list_domains(compact: bool = False, env_file: Optional[str] = None) -> List[Dict]:
    """
    List all domains in account

    Args:
        compact: If True, return compact list (domain names only)
                 If False, return full details

    Returns:
        List of domain objects
    """
    params = {
        'CompactList': 'yes' if compact else 'no'
    }

    data = _make_request('Domain/List', params, env_file)

    if data.get('status') != 'SUCCESS':
        print(f"❌ Error listing domains: {data.get('message', 'Unknown error')}")
        return []

    # Parse domain list
    domains = []

    if compact:
        # Compact format: just domain names
        domain_list = data.get('domain', [])
        if isinstance(domain_list, str):
            domain_list = [domain_list]

        for domain in domain_list:
            domains.append({'domain': domain})
    else:
        # Full format: detailed info
        domain_list = data.get('domain', [])
        if isinstance(domain_list, dict):
            domain_list = [domain_list]

        domains = domain_list

    return domains


def get_domain_info(domain: str, env_file: Optional[str] = None) -> Optional[Dict]:
    """
    Get detailed info for a specific domain

    Args:
        domain: Domain name (e.g., 'example.com')

    Returns:
        Domain info dict or None
    """
    params = {'Domain': domain}

    data = _make_request('Domain/Info', params, env_file)

    if data.get('status') != 'SUCCESS':
        print(f"❌ Error getting domain info for {domain}: {data.get('message', 'Unknown error')}")
        return None

    return data


def check_availability(domain: str, env_file: Optional[str] = None) -> bool:
    """
    Check if domain is available for registration

    Args:
        domain: Domain name to check

    Returns:
        True if available, False otherwise
    """
    params = {'Domain': domain}

    data = _make_request('Domain/Check', params, env_file)

    if data.get('status') != 'SUCCESS':
        return False

    return data.get('available', 'no').lower() == 'yes'


def get_nameservers(domain: str, env_file: Optional[str] = None) -> List[str]:
    """
    Get nameservers for a domain

    Args:
        domain: Domain name

    Returns:
        List of nameserver hostnames
    """
    info = get_domain_info(domain, env_file)

    if not info:
        return []

    nameservers = []
    for i in range(1, 10):
        ns_key = f'nameserver{i}'
        if ns_key in info and info[ns_key]:
            nameservers.append(info[ns_key])

    return nameservers


def update_nameservers(domain: str, nameservers: List[str], env_file: Optional[str] = None) -> Dict:
    """
    Update nameservers for a domain

    Args:
        domain: Domain name
        nameservers: List of nameserver hostnames (2-6)

    Returns:
        Result dict with status
    """
    if len(nameservers) < 2:
        return {'success': False, 'error': 'At least 2 nameservers required'}
    if len(nameservers) > 6:
        nameservers = nameservers[:6]  # Internet.bs max is 6

    params = {'Domain': domain}
    for i, ns in enumerate(nameservers, 1):
        params[f'Ns_list'] = ','.join(nameservers)

    data = _make_request('Domain/Update', params, env_file)

    if data.get('status') == 'SUCCESS':
        return {
            'success': True,
            'domain': domain,
            'nameservers': nameservers,
            'message': 'Nameservers updated'
        }
    else:
        return {
            'success': False,
            'error': data.get('message', 'Unknown error'),
            'transactid': data.get('transactid')
        }


def parse_expiry_date(date_str: str) -> Optional[str]:
    """
    Parse Internet.bs date format to YYYY-MM-DD

    Args:
        date_str: Date string from API (e.g., '11/19/2025')

    Returns:
        ISO format date or None
    """
    if not date_str:
        return None

    try:
        # Internet.bs uses MM/DD/YYYY format
        dt = datetime.strptime(date_str, '%m/%d/%Y')
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        return date_str  # Return as-is if parsing fails


def get_balance(env_file: Optional[str] = None) -> Dict:
    """
    Get account balance across all currencies.

    Returns:
        Dict with 'balances' list [{currency, amount}] and convenience keys
    """
    data = _make_request('/Account/Balance/Get', env_file=env_file)
    balances = data.get('balance', [])
    result = {
        'success': data.get('status') == 'SUCCESS',
        'balances': balances,
    }
    for b in balances:
        result[b['currency'].lower()] = float(b['amount'])
    return result


def get_domain_price(domain: str, currency: str = 'USD', env_file: Optional[str] = None) -> Dict:
    """
    Get registration/renewal price for a domain via availability check.

    Args:
        domain: Domain name to check
        currency: USD or EUR

    Returns:
        Price info dict with currency and amounts
    """
    params = {'Domain': domain, 'Currency': currency}
    data = _make_request('Domain/Check', params, env_file)

    if data.get('status') == 'AVAILABLE' or data.get('status') == 'UNAVAILABLE':
        return {
            'success': True,
            'domain': domain,
            'available': data.get('status') == 'AVAILABLE',
            'currency': currency,
            'price_registration': data.get('registrationprice'),
            'price_renewal': data.get('renewalprice'),
            'price_transfer': data.get('transferprice'),
        }
    else:
        return {
            'success': False,
            'error': data.get('message', 'Unknown error')
        }


def purchase_domain(domain: str, years: int = 1, contacts: Dict = None, env_file: Optional[str] = None) -> Dict:
    """
    Purchase/register a new domain

    Args:
        domain: Domain to register
        years: Registration period (1-10 years)
        contacts: Contact info (registrant, admin, tech, billing)
                  If not provided, uses account default contacts

    Returns:
        Result dict with success status and transaction info

    CRITICAL: This operation costs money. Use with signal gating.
    """
    # First check availability
    if not check_availability(domain, env_file):
        return {
            'success': False,
            'error': f'Domain {domain} is not available for registration'
        }

    params = {
        'Domain': domain,
        'Period': f'{years}Y'
    }

    # Add contacts if provided, otherwise Internet.bs uses account defaults
    if contacts:
        for contact_type in ['Registrant', 'Admin', 'Tech', 'Billing']:
            contact = contacts.get(contact_type.lower(), contacts.get('registrant', {}))
            if contact:
                prefix = f'{contact_type}_'
                for field, value in contact.items():
                    params[f'{prefix}{field}'] = value

    data = _make_request('Domain/Create', params, env_file)

    if data.get('status') == 'SUCCESS':
        return {
            'success': True,
            'domain': domain,
            'years': years,
            'transactid': data.get('transactid'),
            'expiration': data.get('expirationdate'),
            'message': f'Domain {domain} registered for {years} year(s)'
        }
    else:
        return {
            'success': False,
            'error': data.get('message', 'Unknown error'),
            'transactid': data.get('transactid')
        }


def renew_domain(domain: str, years: int = 1, currency: str = 'USD', env_file: Optional[str] = None) -> Dict:
    """
    Renew an existing domain

    Args:
        domain: Domain to renew
        years: Renewal period (1-10 years)
        currency: USD or EUR (default USD — account has USD balance)

    Returns:
        Result dict with success status, price paid, and new expiration

    CRITICAL: This operation costs money. Use with signal gating.
    """
    params = {
        'Domain': domain,
        'Period': f'{years}Y',
        'Currency': currency,
    }

    data = _make_request('Domain/Renew', params, env_file)

    if data.get('status') == 'SUCCESS':
        product = data.get('product', [{}])
        first = product[0] if product else {}
        return {
            'success': True,
            'domain': domain,
            'years': years,
            'currency': data.get('currency', currency),
            'price': data.get('price'),
            'transactid': data.get('transactid'),
            'new_expiration': first.get('newexpiration') or data.get('expirationdate'),
            'paid_until': first.get('paiduntil'),
            'message': f'Domain {domain} renewed for {years} year(s)'
        }
    else:
        return {
            'success': False,
            'domain': domain,
            'error': data.get('message', 'Unknown error'),
            'code': data.get('code'),
            'transactid': data.get('transactid')
        }


if __name__ == '__main__':
    # CLI interface for testing
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Internet.bs operations')
    parser.add_argument('action', choices=['list', 'info', 'check', 'nameservers'])
    parser.add_argument('--domain', help='Domain name')
    parser.add_argument('--compact', action='store_true', help='Compact list (names only)')

    args = parser.parse_args()

    if args.action == 'list':
        domains = list_domains(compact=args.compact)
        print(f"Found {len(domains)} domains:")
        for domain in domains:
            if args.compact:
                print(f"  {domain['domain']}")
            else:
                print(f"  {domain.get('domain', 'N/A')} - Expires: {domain.get('expirationdate', 'N/A')}")

    elif args.action == 'info':
        if not args.domain:
            print("❌ --domain required")
        else:
            info = get_domain_info(args.domain)
            if info:
                print(json.dumps(info, indent=2))

    elif args.action == 'check':
        if not args.domain:
            print("❌ --domain required")
        else:
            available = check_availability(args.domain)
            status = "✅ Available" if available else "❌ Not available"
            print(f"{args.domain}: {status}")

    elif args.action == 'nameservers':
        if not args.domain:
            print("❌ --domain required")
        else:
            nameservers = get_nameservers(args.domain)
            print(f"Nameservers for {args.domain}:")
            for ns in nameservers:
                print(f"  {ns}")
