"""
Web Operations - Search and fetch web content
"""

import json
import re
import os
from typing import List, Dict, Optional
from urllib.parse import quote_plus, urlparse
import httpx
from venice.tools.base import Tools
from venice.core import UI


class WebOpsMixin(Tools):
    """Mixin for web search and fetch operations"""

    def web_search(self, query: str, n_results: int = 5) -> Dict:
        """
        Search the web for current information using Google with Bing fallback.
        """
        self.next_step(f"Searching web for: {query[:50]}...")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

        # Try Google First
        try:
            google_url = f"https://www.google.com/search?q={quote_plus(query)}&num={n_results + 3}"
            with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(google_url)
                if resp.status_code == 200:
                    html = resp.text
                    results = []
                    # Google search result pattern
                    matches = re.findall(r'<div class="g">.*?<a href="([^"]+)"[^>]*>.*?<h3[^>]*>(.*?)</h3>.*?<div[^>]*class="VwiC3b[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
                    
                    for url, title, snippet in matches[:n_results]:
                        if url.startswith('/url?q='):
                            url = url.split('/url?q=')[1].split('&')[0]
                        
                        results.append({
                            "title": re.sub(r'<[^>]+>', '', title).strip(),
                            "url": url,
                            "snippet": re.sub(r'<[^>]+>', '', snippet).strip()
                        })
                    
                    if results:
                        UI.step_done(f"Found {len(results)} results via Google")
                        return {"success": True, "query": query, "results": results, "count": len(results)}

        except Exception as e:
            UI.step_detail(f"Google search failed: {str(e)}. Trying fallback...")

        # Fallback to Bing
        try:
            bing_url = f"https://www.bing.com/search?q={quote_plus(query)}"
            with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(bing_url)
                if resp.status_code == 200:
                    html = resp.text
                    results = []
                    # Bing result pattern
                    matches = re.findall(r'<li class="b_algo">.*?<h2><a href="([^"]+)"[^>]*>(.*?)</a></h2>.*?<div class="b_caption">.*?<p[^>]*>(.*?)</p>', html, re.DOTALL)
                    
                    for url, title, snippet in matches[:n_results]:
                        results.append({
                            "title": re.sub(r'<[^>]+>', '', title).strip(),
                            "url": url,
                            "snippet": re.sub(r'<[^>]+>', '', snippet).strip()
                        })
                    
                    if results:
                        UI.step_done(f"Found {len(results)} results via Bing")
                        return {"success": True, "query": query, "results": results, "count": len(results)}

        except Exception as e:
            return {"success": False, "error": f"All search providers failed: {str(e)}"}

        return {"success": False, "error": "No results found from any provider"}

    def fetch_url(self, url: str, max_length: int = 10000) -> Dict:
        """
        Fetch and extract content from a URL.
        
        Args:
            url: URL to fetch
            max_length: Maximum characters to return (default 10000)
            
        Returns:
            {"success": True, "content": str, "title": str} or {"success": False, "error": str}
        """
        self.next_step(f"Fetching: {url[:60]}...")
        
        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return {"success": False, "error": "Invalid URL"}
            
            # Block dangerous schemes
            if parsed.scheme not in ('http', 'https'):
                return {"success": False, "error": f"Unsupported scheme: {parsed.scheme}"}
            
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; Gondola/2.0)"
                    }
                )
                
                if response.status_code != 200:
                    return {"success": False, "error": f"HTTP {response.status_code}"}
                
                content_type = response.headers.get('content-type', '')
                
                # Handle HTML
                if 'text/html' in content_type:
                    html = response.text
                    
                    # Extract title
                    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
                    title = title_match.group(1).strip() if title_match else "No title"
                    title = re.sub(r'<[^>]+>', '', title)
                    
                    # Extract main content (simple approach)
                    # Remove script and style tags
                    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
                    
                    # Extract text from common content areas
                    content = ""
                    
                    # Try article/main/content tags first
                    for tag in ['article', 'main', '[role="main"]', '.content', '.post', '.entry']:
                        pattern = rf'<{tag}[^>]*>(.*?)</{tag}>' if not tag.startswith('.') and not tag.startswith('[') else rf'{re.escape(tag)}[^>]*>(.*?)</[^>]+>'
                        match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
                        if match:
                            content = match.group(1)
                            break
                    
                    # Fallback to body
                    if not content:
                        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
                        if body_match:
                            content = body_match.group(1)
                    
                    # Clean up HTML
                    content = re.sub(r'<[^>]+>', ' ', content)
                    content = re.sub(r'\s+', ' ', content)
                    content = content.strip()
                    
                    # Truncate if needed
                    if len(content) > max_length:
                        content = content[:max_length] + "\n\n[Content truncated...]"
                    
                    UI.step_done(f"Fetched {len(content)} chars")
                    return {
                        "success": True,
                        "url": url,
                        "title": title,
                        "content": content,
                        "length": len(content)
                    }
                
                # Handle plain text
                elif 'text/plain' in content_type or url.endswith(('.txt', '.md', '.py', '.js', '.json')):
                    content = response.text
                    if len(content) > max_length:
                        content = content[:max_length] + "\n\n[Content truncated...]"
                    
                    UI.step_done(f"Fetched {len(content)} chars")
                    return {
                        "success": True,
                        "url": url,
                        "title": url.split('/')[-1],
                        "content": content,
                        "length": len(content)
                    }
                
                else:
                    return {"success": False, "error": f"Unsupported content type: {content_type}"}
                    
        except httpx.TimeoutException:
            return {"success": False, "error": "Request timed out"}
        except Exception as e:
            return {"success": False, "error": f"Fetch failed: {str(e)}"}

    def search_docs(self, library: str, query: str, version: str = None) -> Dict:
        """
        Search documentation for popular libraries.
        
        Args:
            library: Library name (e.g., 'python', 'react', 'numpy', 'pandas')
            query: What to search for
            version: Specific version (optional)
            
        Returns:
            {"success": True, "results": [...]} or {"success": False, "error": str}
        """
        self.next_step(f"Searching {library} docs for: {query}")
        
        # Map common libraries to their doc URLs
        doc_urls = {
            "python": "docs.python.org",
            "numpy": "numpy.org/doc",
            "pandas": "pandas.pydata.org/docs",
            "react": "react.dev",
            "vue": "vuejs.org",
            "angular": "angular.io",
            "django": "docs.djangoproject.com",
            "flask": "flask.palletsprojects.com",
            "fastapi": "fastapi.tiangolo.com",
            "sqlalchemy": "docs.sqlalchemy.org",
            "requests": "requests.readthedocs.io",
            "httpx": "www.python-httpx.org",
            "pytest": "docs.pytest.org",
            "black": "black.readthedocs.io",
            "mypy": "mypy.readthedocs.io",
            "docker": "docs.docker.com",
            "kubernetes": "kubernetes.io/docs",
            "aws": "docs.aws.amazon.com",
            "gcp": "cloud.google.com/docs",
            "azure": "docs.microsoft.com/azure",
        }
        
        library_lower = library.lower()
        if library_lower not in doc_urls:
            # Try web search instead
            return self.web_search(f"{library} documentation {query}")
        
        # Build search query for the specific docs
        site = doc_urls[library_lower]
        search_query = f"site:{site} {query}"
        
        return self.web_search(search_query)

    def search_stackoverflow(self, query: str, tags: List[str] = None, n_results: int = 5) -> Dict:
        """
        Search Stack Overflow for solutions.
        
        Args:
            query: Search query
            tags: List of tags to filter by (e.g., ['python', 'flask'])
            n_results: Number of results
            
        Returns:
            {"success": True, "questions": [...]} or {"success": False, "error": str}
        """
        self.next_step(f"Searching Stack Overflow: {query[:50]}...")
        
        try:
            # Build search URL
            search_query = query
            if tags:
                search_query += " " + " ".join(f"[{tag}]" for tag in tags)
            
            encoded = quote_plus(search_query)
            url = f"https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=relevance&q={encoded}&site=stackoverflow&pagesize={n_results}"
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                
                if response.status_code != 200:
                    return {"success": False, "error": f"API error: HTTP {response.status_code}"}
                
                data = response.json()
                items = data.get('items', [])
                
                questions = []
                for item in items:
                    questions.append({
                        "title": item.get('title', 'No title'),
                        "url": item.get('link', ''),
                        "score": item.get('score', 0),
                        "answer_count": item.get('answer_count', 0),
                        "is_answered": item.get('is_answered', False),
                        "tags": item.get('tags', []),
                        "views": item.get('view_count', 0)
                    })
                
                UI.step_done(f"Found {len(questions)} questions")
                return {
                    "success": True,
                    "query": query,
                    "questions": questions,
                    "count": len(questions)
                }
                
        except Exception as e:
            return {"success": False, "error": f"Search failed: {str(e)}"}

    def search_github(self, query: str, language: str = None, sort: str = "stars", n_results: int = 5) -> Dict:
        """
        Search GitHub repositories or code.
        
        Args:
            query: Search query
            language: Filter by language (e.g., 'python', 'javascript')
            sort: Sort by 'stars', 'updated', 'best-match'
            n_results: Number of results
            
        Returns:
            {"success": True, "repositories": [...]} or {"success": False, "error": str}
        """
        self.next_step(f"Searching GitHub: {query[:50]}...")
        
        try:
            # Build search query
            search_query = query
            if language:
                search_query += f" language:{language}"
            
            encoded = quote_plus(search_query)
            url = f"https://api.github.com/search/repositories?q={encoded}&sort={sort}&order=desc&per_page={n_results}"
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                
                if response.status_code == 403:
                    return {"success": False, "error": "GitHub API rate limit exceeded"}
                
                if response.status_code != 200:
                    return {"success": False, "error": f"API error: HTTP {response.status_code}"}
                
                data = response.json()
                items = data.get('items', [])
                
                repos = []
                for item in items:
                    repos.append({
                        "name": item.get('full_name', 'Unknown'),
                        "url": item.get('html_url', ''),
                        "description": item.get('description', ''),
                        "stars": item.get('stargazers_count', 0),
                        "language": item.get('language', 'Unknown'),
                        "updated": item.get('updated_at', ''),
                        "forks": item.get('forks_count', 0),
                        "open_issues": item.get('open_issues_count', 0)
                    })
                
                UI.step_done(f"Found {len(repos)} repositories")
                return {
                    "success": True,
                    "query": query,
                    "repositories": repos,
                    "count": len(repos),
                    "total_count": data.get('total_count', 0)
                }
                
        except Exception as e:
            return {"success": False, "error": f"Search failed: {str(e)}"}

    def download_placeholder_image(self, keyword: str = None, width: int = 800, height: int = 600, 
                                    service: str = "picsum", filename: str = None, 
                                    grayscale: bool = False, blur: int = 0) -> Dict:
        """
        Download a placeholder image for web design from free placeholder services.
        
        Supported services:
        - picsum: Random photos from Unsplash (default)
        - placehold: Solid color with text overlay
        - via: Random images with custom text
        
        Args:
            keyword: Optional keyword for image selection (picsum only, affects seed)
            width: Image width in pixels (default 800)
            height: Image height in pixels (default 600)
            service: Placeholder service - 'picsum', 'placehold', or 'via' (default 'picsum')
            filename: Output filename (default: 'placeholder_{width}x{height}.jpg')
            grayscale: Convert to grayscale (picsum only)
            blur: Blur amount 1-10 (picsum only)
            
        Returns:
            {"success": True, "filename": str, "url": str, "size": int} or {"success": False, "error": str}
        """
        self.next_step(f"Downloading placeholder image ({width}x{height})")
        
        try:
            # Validate dimensions
            if not (1 <= width <= 4000) or not (1 <= height <= 4000):
                return {"success": False, "error": "Width and height must be between 1 and 4000"}
            
            # Build URL based on service
            if service == "picsum":
                # Lorem Picsum - random photos
                seed = keyword or "random"
                url = f"https://picsum.photos/seed/{seed}/{width}/{height}"
                if grayscale:
                    url += "?grayscale"
                if blur > 0 and blur <= 10:
                    separator = "&" if grayscale else "?"
                    url += f"{separator}blur={blur}"
                ext = "jpg"
                
            elif service == "placehold":
                # Placehold.co - solid color with text
                text = keyword or f"{width}x{height}"
                url = f"https://placehold.co/{width}x{height}?text={quote_plus(text)}"
                ext = "png"
                
            elif service == "via":
                # Via.placeholder - custom text
                text = keyword or "Placeholder"
                url = f"https://via.placeholder.com/{width}x{height}?text={quote_plus(text)}"
                ext = "png"
                
            else:
                return {"success": False, "error": f"Unknown service: {service}. Use 'picsum', 'placehold', or 'via'"}
            
            # Determine output filename
            if not filename:
                filename = f"placeholder_{width}x{height}.{ext}"
            
            # Ensure filename is within workspace
            output_path = self.workspace._resolve(filename)
            
            # Download image
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; Gondola/2.0)"
                    }
                )
                
                if response.status_code != 200:
                    return {"success": False, "error": f"Download failed: HTTP {response.status_code}"}
                
                # Save to file
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                file_size = len(response.content)
                
                UI.step_detail(f"Saved: {filename}")
                UI.step_detail(f"Size: {file_size:,} bytes")
                UI.step_detail(f"URL: {url}")
                UI.step_done("Image downloaded")
                
                return {
                    "success": True,
                    "filename": filename,
                    "path": output_path,
                    "url": url,
                    "size": file_size,
                    "width": width,
                    "height": height,
                    "service": service
                }
                
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": f"Download failed: {str(e)}"}

    def download_image(self, url: str, filename: str = None) -> Dict:
        """
        Smart download: works with direct image URLs or webpage URLs (hunts for the main image).
        """
        self.next_step(f"Processing image request: {url[:60]}...")
        
        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return {"success": False, "error": "Invalid URL"}
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": f"{parsed.scheme}://{parsed.netloc}/"
            }

            target_url = url
            is_direct = any(url.lower().split('?')[0].endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'])

            if not is_direct:
                UI.step_detail("URL looks like a webpage. Hunting for main image...")
                with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        html = resp.text
                        
                        # 1. Look for OpenGraph image
                        og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                        if not og_match:
                            og_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.IGNORECASE)
                        
                        # 2. Look for Twitter image
                        if not og_match:
                            og_match = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)

                        # 3. Look for large images in <img> tags (heuristic)
                        if not og_match:
                            img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|jpeg|png|webp))["\']', html, re.IGNORECASE)
                            if img_matches:
                                # Prioritize images with 'hero', 'main', or 'product' in name
                                for img in img_matches:
                                    if any(word in img.lower() for word in ['hero', 'main', 'product', 'full']):
                                        target_url = img
                                        break
                                if target_url == url: target_url = img_matches[0]

                        if og_match:
                            found_url = og_match.group(1)
                            if found_url.startswith('//'): found_url = 'https:' + found_url
                            elif found_url.startswith('/'): found_url = f"{parsed.scheme}://{parsed.netloc}{found_url}"
                            target_url = found_url
                            UI.step_detail(f"Found 'hero' image: {target_url[:60]}...")

            # Final download logic
            with httpx.Client(timeout=60.0, follow_redirects=True, headers=headers) as client:
                response = client.get(target_url)
                
                if response.status_code != 200:
                    return {"success": False, "error": f"Download failed: HTTP {response.status_code}"}
                
                # Check content type
                content_type = response.headers.get('content-type', '')
                if 'image' not in content_type:
                    # Some sites serve images with generic octet-stream
                    if 'application/octet-stream' not in content_type:
                        return {"success": False, "error": f"Resulting URL is not an image (Content-Type: {content_type})"}

                # Determine filename
                if not filename:
                    filename = os.path.basename(urlparse(target_url).path)
                    if not filename or '.' not in filename:
                        filename = "downloaded_photo.jpg"
                
                output_path = self.workspace._resolve(filename)
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                UI.step_done(f"Saved: {filename} ({len(response.content):,} bytes)")
                
                return {
                    "success": True,
                    "filename": filename,
                    "path": str(output_path),
                    "source_url": target_url,
                    "size": len(response.content)
                }
                
        except Exception as e:
            UI.step_error(str(e))
            return {"success": False, "error": str(e)}

    def image_search(self, query: str, n_results: int = 10) -> Dict:
        """
        Search for images using Bing Images (easier to scrape direct links).
        """
        self.next_step(f"Hunting for images: {query[:50]}...")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Referer": "https://www.bing.com/"
        }

        try:
            url = f"https://www.bing.com/images/search?q={quote_plus(query)}&first=1"
            with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    return {"success": False, "error": f"Image search failed: HTTP {resp.status_code}"}
                
                html = resp.text
                images = []
                matches = re.findall(r'm="([^"]+)"', html)
                
                for m_json in matches:
                    try:
                        data_str = m_json.replace('&quot;', '"')
                        data = json.loads(data_str)
                        img_url = data.get('murl')
                        
                        if img_url and img_url not in [i['url'] for i in images]:
                            images.append({
                                "title": data.get('t', 'Image'),
                                "url": img_url,
                                "type": "direct",
                                "thumbnail": data.get('turl')
                            })
                            if len(images) >= n_results:
                                break
                    except:
                        continue

                if not images:
                    return self.web_search(f"{query} image direct link", n_results=n_results)

                UI.step_done(f"Found {len(images)} direct image links")
                return {"success": True, "query": query, "images": images}
                
        except Exception as e:
            return {"success": False, "error": f"Image search failed: {str(e)}"}
