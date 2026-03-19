import asyncio
import aiohttp
from usp.tree import sitemap_from_str
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    url = "https://flowwow.com/moscow/sitemap.xml"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            print(f"Status: {response.status}")
            print(f"Content-Type: {response.headers.get('Content-Type')}")
            content = await response.text()
            print(f"Content length: {len(content)}")
            
            try:
                sitemap = sitemap_from_str(content)
                print(f"Sitemap type: {type(sitemap)}")
                
                if hasattr(sitemap, 'sub_sitemaps'):
                    print(f"Sub sitemaps count: {len(sitemap.sub_sitemaps)}")
                    for sub in sitemap.sub_sitemaps[:5]:
                        print(f"  - {sub.url}")
                
                if hasattr(sitemap, 'pages'):
                    print(f"Pages count: {len(sitemap.pages)}")
            except Exception as e:
                print(f"Error parsing: {e}")

if __name__ == "__main__":
    asyncio.run(main())