"""
Web Scraper Service

Handles web scraping operations:
- Single page scraping
- Sitemap-based scraping
- Content extraction and cleaning
- Rate limiting and robots.txt compliance
"""

import logging
import re
import asyncio
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse, urlunparse
from datetime import datetime
import xml.etree.ElementTree as ET

from app.config import settings

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logging.warning("httpx not installed. Web scraping will not be available.")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logging.warning("beautifulsoup4 not installed. HTML parsing will not be available.")

from app.config import settings

logger = logging.getLogger(__name__)


class WebScraper:
    """
    Web scraper for extracting content from websites.
    """
    
    def __init__(
        self,
        max_pages: int = None,
        timeout: int = 30,
        follow_links: bool = True
    ):
        """
        Initialize web scraper.
        
        Args:
            max_pages: Maximum number of pages to scrape
            timeout: Request timeout in seconds
            follow_links: Whether to follow links on pages
        """
        if not HTTPX_AVAILABLE:
            raise RuntimeError("httpx is required for web scraping")
        if not BS4_AVAILABLE:
            raise RuntimeError("beautifulsoup4 is required for HTML parsing")
        
        self.max_pages = max_pages or settings.MAX_PAGES_TO_SCRAPE
        self.timeout = timeout
        self.follow_links = follow_links
        self.visited_urls: Set[str] = set()
        self.failed_urls: Dict[str, str] = {}
        
    # ========================================================================
    # URL UTILITIES
    # ========================================================================
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize URL (remove fragments, trailing slashes, etc.).
        
        Args:
            url: URL to normalize
            
        Returns:
            str: Normalized URL
        """
        parsed = urlparse(url)
        
        # Remove fragment
        parsed = parsed._replace(fragment='')
        
        # Remove trailing slash from path
        path = parsed.path.rstrip('/')
        if not path:
            path = '/'
        parsed = parsed._replace(path=path)
        
        return urlunparse(parsed)
    
    def is_same_domain(self, url1: str, url2: str) -> bool:
        """
        Check if two URLs are from the same domain.
        
        Args:
            url1: First URL
            url2: Second URL
            
        Returns:
            bool: True if same domain
        """
        domain1 = urlparse(url1).netloc
        domain2 = urlparse(url2).netloc
        return domain1 == domain2
    
    def is_valid_url(self, url: str) -> bool:
        """
        Validate URL format.
        
        Args:
            url: URL to validate
            
        Returns:
            bool: True if valid
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    # ========================================================================
    # ROBOTS.TXT HANDLING
    # ========================================================================
    
    async def check_robots_txt(self, base_url: str, path: str = "/") -> bool:
        """
        Check if URL is allowed by robots.txt.
        
        Args:
            base_url: Base URL of website
            path: Path to check
            
        Returns:
            bool: True if allowed (or robots.txt not found)
        """
        # If robots.txt respect is disabled, always allow
        if not settings.RESPECT_ROBOTS_TXT:
            return True
            
        try:
            robots_url = urljoin(base_url, "/robots.txt")
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(robots_url)
                
                if response.status_code == 404:
                    return True  # No robots.txt, allow scraping
                
                if response.status_code == 200:
                    # Simple robots.txt parsing (check for Disallow)
                    robots_content = response.text
                    
                    # Check if path is disallowed
                    for line in robots_content.splitlines():
                        line = line.strip()
                        if line.startswith('Disallow:'):
                            disallowed_path = line.split(':', 1)[1].strip()
                            if path.startswith(disallowed_path):
                                return False
                    
                    return True
        except Exception as e:
            logger.warning(f"Error checking robots.txt: {str(e)}")
            return True  # Allow on error
    
    # ========================================================================
    # SITEMAP PARSING
    # ========================================================================
    
    async def get_sitemap_urls(self, sitemap_url: str) -> List[str]:
        """
        Extract URLs from sitemap.xml.
        
        Args:
            sitemap_url: URL of sitemap
            
        Returns:
            List[str]: List of URLs from sitemap
        """
        urls = []
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(sitemap_url)
                
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch sitemap: {response.status_code}")
                    return urls
                
                # Parse XML
                root = ET.fromstring(response.content)
                
                # Handle different sitemap namespaces
                namespaces = {
                    'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                    'news': 'http://www.google.com/schemas/sitemap-news/0.9',
                    'image': 'http://www.google.com/schemas/sitemap-image/1.1'
                }
                
                # Extract URLs
                for url_elem in root.findall('.//sm:url/sm:loc', namespaces):
                    url = url_elem.text
                    if url:
                        urls.append(url)
                
                # Handle sitemap index (sitemaps of sitemaps)
                for sitemap_elem in root.findall('.//sm:sitemap/sm:loc', namespaces):
                    sitemap_loc = sitemap_elem.text
                    if sitemap_loc:
                        # Recursively get URLs from sub-sitemaps
                        sub_urls = await self.get_sitemap_urls(sitemap_loc)
                        urls.extend(sub_urls)
                
                logger.info(f"Found {len(urls)} URLs in sitemap")
                
        except Exception as e:
            logger.error(f"Error parsing sitemap {sitemap_url}: {str(e)}")
        
        return urls
    
    async def discover_sitemap(self, base_url: str) -> Optional[str]:
        """
        Try to discover sitemap URL for a website.
        
        Args:
            base_url: Base URL of website
            
        Returns:
            Optional[str]: Sitemap URL if found
        """
        common_sitemap_paths = [
            '/sitemap.xml',
            '/sitemap_index.xml',
            '/sitemap1.xml',
            '/sitemap-index.xml'
        ]
        
        for path in common_sitemap_paths:
            sitemap_url = urljoin(base_url, path)
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.head(sitemap_url)
                    if response.status_code == 200:
                        logger.info(f"Discovered sitemap: {sitemap_url}")
                        return sitemap_url
            except:
                continue
        
        logger.info(f"No sitemap found for {base_url}")
        return None
    
    # ========================================================================
    # PAGE SCRAPING
    # ========================================================================
    
    async def scrape_page(self, url: str) -> Dict[str, Any]:
        """
        Scrape a single web page.
        
        Args:
            url: URL to scrape
            
        Returns:
            Dict: Scraped page data
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True
            ) as client:
                response = await client.get(url)
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "url": url,
                        "status_code": response.status_code,
                        "error": f"HTTP {response.status_code}"
                    }
                
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract title
                title = None
                if soup.title:
                    title = soup.title.string
                elif soup.find('h1'):
                    title = soup.find('h1').get_text().strip()
                
                # Extract content
                content = self._extract_content(soup)
                
                # Extract links if following links
                links = []
                if self.follow_links:
                    links = self._extract_links(soup, url)
                
                # Extract metadata
                metadata = self._extract_metadata(soup)
                
                return {
                    "success": True,
                    "url": url,
                    "title": title,
                    "content": content,
                    "links": links,
                    "metadata": metadata,
                    "status_code": response.status_code,
                    "scraped_at": datetime.utcnow().isoformat()
                }
                
        except httpx.TimeoutException:
            logger.error(f"Timeout scraping {url}")
            return {
                "success": False,
                "url": url,
                "error": "Request timeout"
            }
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            return {
                "success": False,
                "url": url,
                "error": str(e)
            }
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """
        Extract main content from HTML.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            str: Extracted text content
        """
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript']):
            element.decompose()
        
        # Try to find main content area
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile('content|main'))
        
        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
        else:
            text = soup.get_text(separator='\n', strip=True)
        
        # Clean text
        text = self._clean_text(text)
        
        return text
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract all links from page.
        
        Args:
            soup: BeautifulSoup object
            base_url: Base URL for resolving relative links
            
        Returns:
            List[str]: List of absolute URLs
        """
        links = []
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            # Skip anchors, javascript, mailto, etc.
            if href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            
            # Convert to absolute URL
            absolute_url = urljoin(base_url, href)
            
            # Normalize
            absolute_url = self.normalize_url(absolute_url)
            
            # Only include same-domain links
            if self.is_same_domain(absolute_url, base_url):
                links.append(absolute_url)
        
        return list(set(links))  # Remove duplicates
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract metadata from HTML.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Dict: Metadata
        """
        metadata = {}
        
        # Meta description
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag and desc_tag.get('content'):
            metadata['description'] = desc_tag['content']
        
        # Meta keywords
        keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
        if keywords_tag and keywords_tag.get('content'):
            metadata['keywords'] = keywords_tag['content']
        
        # Author
        author_tag = soup.find('meta', attrs={'name': 'author'})
        if author_tag and author_tag.get('content'):
            metadata['author'] = author_tag['content']
        
        # Open Graph tags
        og_tags = soup.find_all('meta', property=re.compile('^og:'))
        for tag in og_tags:
            if tag.get('property') and tag.get('content'):
                key = tag['property'].replace('og:', '')
                metadata[f'og_{key}'] = tag['content']
        
        return metadata
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text.
        
        Args:
            text: Text to clean
            
        Returns:
            str: Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove excessive newlines
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Trim
        text = text.strip()
        
        return text
    
    # ========================================================================
    # BATCH SCRAPING
    # ========================================================================
    
    async def scrape_website(
        self,
        start_url: str,
        use_sitemap: bool = True
    ) -> Dict[str, Any]:
        """
        Scrape multiple pages from a website.
        
        Args:
            start_url: Starting URL
            use_sitemap: Whether to try using sitemap
            
        Returns:
            Dict: Scraping results
        """
        results = {
            "success": True,
            "start_url": start_url,
            "pages": [],
            "failed_pages": [],
            "total_pages": 0,
            "successful_pages": 0,
            "failed_count": 0
        }
        
        urls_to_scrape = []
        
        # Try to get URLs from sitemap
        if use_sitemap:
            sitemap_url = await self.discover_sitemap(start_url)
            if sitemap_url:
                sitemap_urls = await self.get_sitemap_urls(sitemap_url)
                urls_to_scrape.extend(sitemap_urls[:self.max_pages])
        
        # If no sitemap or not enough URLs, add start URL
        if not urls_to_scrape:
            urls_to_scrape.append(start_url)
        
        # Limit to max_pages
        urls_to_scrape = urls_to_scrape[:self.max_pages]
        
        logger.info(f"Scraping {len(urls_to_scrape)} pages from {start_url}")
        
        # Scrape pages
        for url in urls_to_scrape:
            if len(results["pages"]) >= self.max_pages:
                break
            
            if url in self.visited_urls:
                continue
            
            # Check robots.txt before scraping
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            path = parsed_url.path or "/"
            
            if not await self.check_robots_txt(base_url, path):
                logger.info(f"Skipping {url} - disallowed by robots.txt")
                results["failed_pages"].append({
                    "url": url,
                    "error": "Disallowed by robots.txt"
                })
                results["failed_count"] += 1
                continue
            
            self.visited_urls.add(url)
            
            # Scrape page
            page_result = await self.scrape_page(url)
            
            if page_result.get("success"):
                results["pages"].append(page_result)
                results["successful_pages"] += 1
                
                # Add discovered links to queue (if following links and not using sitemap)
                if self.follow_links and not use_sitemap:
                    for link in page_result.get("links", []):
                        if link not in self.visited_urls and link not in urls_to_scrape:
                            if len(urls_to_scrape) < self.max_pages:
                                urls_to_scrape.append(link)
            else:
                results["failed_pages"].append({
                    "url": url,
                    "error": page_result.get("error", "Unknown error")
                })
                results["failed_count"] += 1
            
            # Small delay to be respectful
            await asyncio.sleep(0.5)
        
        results["total_pages"] = len(results["pages"]) + len(results["failed_pages"])
        
        # Mark as failed if no pages were successfully scraped
        if results["successful_pages"] == 0:
            results["success"] = False
            results["error"] = "No pages were successfully scraped"
        
        logger.info(
            f"Scraping complete: {results['successful_pages']} successful, "
            f"{results['failed_count']} failed"
        )
        
        return results


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def scrape_single_page(url: str) -> Dict[str, Any]:
    """
    Scrape a single page (convenience function).
    
    Args:
        url: URL to scrape
        
    Returns:
        Dict: Page data
    """
    scraper = WebScraper(max_pages=1, follow_links=False)
    return await scraper.scrape_page(url)


async def scrape_sitemap(sitemap_url: str, max_pages: int = 10) -> List[Dict[str, Any]]:
    """
    Scrape pages from a sitemap (convenience function).
    
    Args:
        sitemap_url: URL of sitemap
        max_pages: Maximum pages to scrape
        
    Returns:
        List[Dict]: List of scraped pages
    """
    scraper = WebScraper(max_pages=max_pages, follow_links=False)
    urls = await scraper.get_sitemap_urls(sitemap_url)
    
    pages = []
    for url in urls[:max_pages]:
        page_data = await scraper.scrape_page(url)
        if page_data.get("success"):
            pages.append(page_data)
        await asyncio.sleep(0.5)
    
    return pages


# ============================================================================
# SINGLETON PATTERN FOR WEB SCRAPER
# ============================================================================

_scraper_instance = None
_scraper_lock = asyncio.Lock()


async def get_web_scraper(
    max_pages: int = None,
    timeout: int = 30,
    follow_links: bool = True,
    force_new: bool = False
) -> WebScraper:
    """
    Get or create a singleton WebScraper instance.
    
    The scraper is reused across requests to avoid re-initialization overhead.
    Settings can be updated on the existing instance.
    
    Args:
        max_pages: Maximum number of pages to scrape
        timeout: Request timeout in seconds
        follow_links: Whether to follow links on pages
        force_new: Force creation of new instance
        
    Returns:
        WebScraper: Scraper instance
    """
    global _scraper_instance
    
    async with _scraper_lock:
        if _scraper_instance is None or force_new:
            logger.info("Initializing WebScraper singleton...")
            _scraper_instance = WebScraper(
                max_pages=max_pages,
                timeout=timeout,
                follow_links=follow_links
            )
            logger.info("WebScraper singleton initialized successfully")
        else:
            # Update settings on existing instance
            if max_pages is not None:
                _scraper_instance.max_pages = max_pages
            if timeout is not None:
                _scraper_instance.timeout = timeout
            if follow_links is not None:
                _scraper_instance.follow_links = follow_links
            
            # Reset visited URLs for new scraping session
            _scraper_instance.visited_urls.clear()
            _scraper_instance.failed_urls.clear()
            
            logger.debug("Reusing existing WebScraper instance with updated settings")
    
    return _scraper_instance

