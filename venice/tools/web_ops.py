"""
Web Operations - Search and fetch web content
"""

import json
import re
from typing import List, Dict, Optional
from urllib.parse import quote_plus, urlparse
import httpx
from venice.tools.base import Tools
from venice.core import UI


class WebOpsMixin(Tools):
    """Mixin for web search and fetch operations"""

    def web_search(self, query: str, n_results: int = 5) -> Dict:
        """
        Search the web for current information.
        
        Uses DuckDuckGo (no API key required) or falls back to other search engines.
        
        Args:
            query: Search query
            n_results: Number of results to return (default 5)
            
        Returns:
            {"success": True, "results": [...]} or {"success": False, "error": str}
        """
        self.next_step(f"Searching web for: {query[:50]}...")
        
        try:
            # Try DuckDuckGo HTML scraping (no API key needed)
            ddg_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(
                    ddg_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
                
                if response.status_code != 200:
                    return {"success": False, "error": f"Search failed: HTTP {response.status_code}"}
                
                html = response.text
                
                # Parse results
                results = []
                
                # DuckDuckGo result pattern
                result_pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
                snippet_pattern = r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>'
                
                urls = re.findall(result_pattern, html, re.DOTALL | re.IGNORECASE)
                snippets = re.findall(snippet_pattern, html, re.DOTALL | re.IGNORECASE)
                
                for i, (url, title) in enumerate(urls[:n_results]):
                    if url.startswith('//'):
                        url = 'https:' + url
                    elif url.startswith('/'):
                        continue  # Skip internal links
                    
                    # Clean up title
                    title = re.sub(r'<[^>]+>', '', title)
                    title = title.strip()
                    
                    snippet = ""
                    if i < len(snippets):
                        snippet = re.sub(r'<[^>]+>', '', snippets[i])
                        snippet = snippet.strip()
                    
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet
                    })
                
                if not results:
                    # Try alternative parsing
                    alt_pattern = r'<h[^>]*class="result__title"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
                    alt_matches = re.findall(alt_pattern, html, re.DOTALL | re.IGNORECASE)
                    
                    for url, title in alt_matches[:n_results]:
                        if url.startswith('http'):
                            title = re.sub(r'<[^>]+>', '', title)
                            results.append({
                                "title": title.strip(),
                                "url": url,
                                "snippet": ""
                            })
                
                UI.step_done(f"Found {len(results)} results")
                return {
                    "success": True,
                    "query": query,
                    "results": results,
                    "count": len(results)
                }
                
        except Exception as e:
            return {"success": False, "error": f"Search failed: {str(e)}"}

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
