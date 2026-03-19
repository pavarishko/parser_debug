"""Command-line interface for website audit tool."""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import List

from models import DomainInput, AuditResult
from analyzer import analyze_batch, analyze_batch_streaming


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )


def load_domains(input_file: str) -> List[DomainInput]:
    """
    Load domains from input file (JSON or JSONL).
    
    Args:
        input_file: Path to input file
        
    Returns:
        List of DomainInput objects
    """
    path = Path(input_file)
    
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    if not content:
        return []
    
    # Parse domain entry
    def parse_entry(obj: dict) -> DomainInput:
        # Try various field names for domain
        domain = (
            obj.get('domain') or 
            obj.get('Domain') or 
            obj.get('host') or 
            obj.get('Host') or 
            ''
        ).strip()
        
        tier = obj.get('curr_gmv_tier') or obj.get('tier')
        industry = obj.get('curr_industry') or obj.get('industry')
        
        return DomainInput(
            domain=domain,
            curr_gmv_tier=str(tier).strip() if tier else None,
            curr_industry=str(industry).strip() if industry else None,
        )
    
    # Detect format: JSON array or JSONL
    if content.startswith('['):
        # JSON array
        data = json.loads(content)
        domains = [parse_entry(obj) for obj in data if isinstance(obj, dict)]
    else:
        # JSONL (one JSON object per line)
        domains = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                domains.append(parse_entry(obj))
    
    # Filter out empty domains
    return [d for d in domains if d.domain]


def save_results(results: List[AuditResult], output_file: str, format: str):
    """
    Save results to output file.
    
    Args:
        results: List of AuditResult objects
        output_file: Path to output file
        format: Output format (json or jsonl)
    """
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        if format == 'json':
            # JSON array with indentation
            json.dump(
                [r.to_dict() for r in results],
                f,
                ensure_ascii=False,
                indent=2
            )
        else:
            # JSONL (one object per line)
            for result in results:
                f.write(json.dumps(result.to_dict(), ensure_ascii=False) + '\n')


def progress_callback(completed: int, total: int):
    """Print progress to stderr."""
    percent = (completed / total) * 100 if total > 0 else 0
    print(f"\rProgress: {completed}/{total} ({percent:.1f}%)", end='', file=sys.stderr)
    if completed == total:
        print(file=sys.stderr)  # New line at end


async def run_audit(args):
    """Run the audit with provided arguments."""
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # Load domains
    logger.info(f"Loading domains from {args.input}")
    domains = load_domains(args.input)
    logger.info(f"Loaded {len(domains)} domains")
    
    if not domains:
        logger.error("No domains to analyze")
        return 1
    
    # Prepare output file for incremental writes
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Open output file for writing results incrementally
    output_file = open(output_path, 'w', encoding='utf-8')
    results = []
    
    def save_and_track_progress(result: AuditResult, completed: int, total: int):
        """Save result immediately and track progress."""
        # Write to file immediately
        output_file.write(json.dumps(result.to_dict(), ensure_ascii=False) + '\n')
        output_file.flush()  # Ensure written to disk
        
        # Track for summary
        results.append(result)
        
        # Show progress
        if not args.quiet:
            progress_callback(completed, total)
    
    try:
        # Run analysis
        sitemap_mode = "FULL" if args.full_sitemap_parsing else "FAST"
        logger.info(f"Starting analysis with concurrency={args.concurrency}, delay={args.delay}s, sitemap_mode={sitemap_mode}")
        
        await analyze_batch_streaming(
            domains=domains,
            output_callback=save_and_track_progress,
            concurrency=args.concurrency,
            domain_delay=args.delay,
            timeout=args.timeout,
            max_retries=args.retries,
            fast_sitemap_mode=not args.full_sitemap_parsing,
        )
        
    finally:
        output_file.close()
    
    # Print summary
    if not args.quiet:
        successful = sum(1 for r in results if r.home_accessible)
        robots_found = sum(1 for r in results if r.robots and r.robots.exists)
        sitemap_found = sum(1 for r in results if r.sitemap and r.sitemap.exists)
        cms_detected = sum(1 for r in results if r.cms and r.cms.detected)
        
        print(f"\n=== Audit Summary ===", file=sys.stderr)
        print(f"Total domains:      {len(results)}", file=sys.stderr)
        print(f"Accessible:         {successful} ({successful/len(results)*100:.1f}%)", file=sys.stderr)
        print(f"Robots.txt found:   {robots_found} ({robots_found/len(results)*100:.1f}%)", file=sys.stderr)
        print(f"Sitemap found:      {sitemap_found} ({sitemap_found/len(results)*100:.1f}%)", file=sys.stderr)
        print(f"CMS detected:       {cms_detected} ({cms_detected/len(results)*100:.1f}%)", file=sys.stderr)
    
    logger.info("Audit complete")
    return 0


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description='Website Technical Infrastructure Audit Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python -m cli -i domains.json -o results.json
  
  # High concurrency with custom delay
  python -m cli -i domains.jsonl -o results.jsonl -c 100 -d 0.5
  
  # Verbose output with JSON format
  python -m cli -i domains.json -o results.json -v --format json
  
  # Custom timeout and retries
  python -m cli -i domains.json -o results.json -t 30 -r 3
        """
    )
    
    # Input/Output
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Input file with domains (JSON or JSONL format)'
    )
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Output file for results'
    )
    parser.add_argument(
        '-f', '--format',
        choices=['json', 'jsonl'],
        default='jsonl',
        help='Output format (default: jsonl)'
    )
    
    # Performance
    parser.add_argument(
        '-c', '--concurrency',
        type=int,
        default=50,
        help='Maximum concurrent requests (default: 50)'
    )
    parser.add_argument(
        '-d', '--delay',
        type=float,
        default=1.0,
        help='Delay between requests to same domain in seconds (default: 1.0)'
    )
    parser.add_argument(
        '-t', '--timeout',
        type=float,
        default=15.0,
        help='Request timeout in seconds (default: 15.0)'
    )
    parser.add_argument(
        '-r', '--retries',
        type=int,
        default=2,
        help='Maximum retry attempts for failed requests (default: 2)'
    )
    
    # Sitemap parsing mode
    parser.add_argument(
        '--full-sitemap-parsing',
        action='store_true',
        help='Enable full sitemap parsing (extracts all URLs). Default is fast mode (checks existence only).'
    )
    
    # Logging
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress progress output'
    )
    
    args = parser.parse_args()
    
    # Run audit
    try:
        exit_code = asyncio.run(run_audit(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()