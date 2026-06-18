#!/usr/bin/env python3
"""
Product Key Generator

Generates product keys for PharmaSUD pharmacies.
Keys are typed for human readability but NOT tied to pharmacy type.

Format: PHARM-<UUID4_HEX_12>

Usage:
    python scripts/generate_product_keys.py --count 10 --prefix PHARM
    python scripts/generate_product_keys.py --count 5 --label "Demo Batch"
"""

import argparse
import uuid
import json
import sys
from datetime import datetime
from pathlib import Path


def generate_product_key(prefix: str = "PHARM") -> str:
    """Generate a single product key."""
    # Use UUID4 for cryptographic randomness
    # Take first 12 chars of hex for readability
    unique_part = uuid.uuid4().hex[:12].upper()
    return f"{prefix}-{unique_part}"


def generate_keys(count: int, prefix: str = "PHARM", label: str = "") -> list:
    """Generate multiple product keys."""
    keys = []
    for i in range(count):
        key = generate_product_key(prefix)
        keys.append({
            "key": key,
            "prefix": prefix,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "sequence": i + 1,
            "label": label
        })
    return keys


def main():
    parser = argparse.ArgumentParser(
        description="Generate PharmaSUD product keys",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/generate_product_keys.py --count 10
  python scripts/generate_product_keys.py --count 5 --label "Customer Batch #1"
  python scripts/generate_product_keys.py --count 1 --prefix DEMO
"""
    )
    parser.add_argument(
        '-c', '--count',
        type=int,
        default=1,
        help='Number of keys to generate (default: 1)'
    )
    parser.add_argument(
        '-p', '--prefix',
        default='PHARM',
        help='Key prefix (default: PHARM)'
    )
    parser.add_argument(
        '-l', '--label',
        default='',
        help='Optional label for this batch of keys'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output JSON file path (default: stdout)'
    )
    parser.add_argument(
        '--csv',
        action='store_true',
        help='Also output CSV format to stdout'
    )

    args = parser.parse_args()

    if args.count < 1 or args.count > 1000:
        print("Error: count must be between 1 and 1000", file=sys.stderr)
        sys.exit(1)

    keys = generate_keys(args.count, args.prefix, args.label)

    # Output JSON
    output_data = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total": len(keys),
        "prefix": args.prefix,
        "label": args.label,
        "keys": keys
    }

    json_output = json.dumps(output_data, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(json_output, encoding='utf-8')
        print(f"Written {len(keys)} keys to {args.output}")
    else:
        print(json_output)

    if args.csv:
        print("\n--- CSV ---", file=sys.stderr)
        print("key,prefix,generated_at,sequence,label")
        for k in keys:
            print(f"{k['key']},{k['prefix']},{k['generated_at']},{k['sequence']},{args.label}")


if __name__ == '__main__':
    main()
