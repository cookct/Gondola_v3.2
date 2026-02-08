"""
Project Index - Compressed project understanding for cheap models.

Scans a project once and builds a compact representation that fits
in ~1000 tokens, enabling models to understand large codebases
without loading every file.
"""

import os
import re
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False


class ProjectIndex:
    """
    Builds and maintains a compressed index of a project.

    Key features:
    - Directory tree structure
    - One-line summaries per file (based on content analysis)
    - Key symbols (functions, classes) per file
    - Import/dependency graph
    - Task-aware file retrieval
    - Semantic search with local embeddings
    """

    # File patterns to ignore
    IGNORE_PATTERNS = {
        '.git', '__pycache__', 'node_modules', '.venv', 'venv',
        '.env', '.idea', '.vscode', 'dist', 'build', '.next',
        '*.pyc', '*.pyo', '*.egg-info', '.DS_Store', 'package-lock.json',
        'yarn.lock', '*.min.js', '*.min.css', '*.map'
    }

    # File extensions we care about for code analysis
    CODE_EXTENSIONS = {
        '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css',
        '.json', '.yaml', '.yml', '.md', '.sh', '.sql'
    }

    # Keywords for task matching
    TASK_KEYWORDS = {
        'settings': ['settings', 'config', 'preferences', 'options'],
        'auth': ['auth', 'login', 'user', 'session', 'token', 'password'],
        'ui': ['component', 'view', 'page', 'render', 'display', 'ui', 'widget'],
        'api': ['api', 'endpoint', 'route', 'request', 'response', 'fetch'],
        'database': ['model', 'schema', 'database', 'db', 'query', 'sql'],
        'test': ['test', 'spec', 'mock', 'fixture'],
        'style': ['style', 'css', 'theme', 'color', 'layout'],
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        self.structure: Dict[str, List[str]] = {}  # dir -> [files]
        self.file_summaries: Dict[str, str] = {}   # file -> one-line summary
        self.symbols: Dict[str, Dict] = {}         # file -> {functions, classes}
        self.dependencies: Dict[str, Set[str]] = {}  # file -> set of imported files
        self.file_hashes: Dict[str, str] = {}      # file -> content hash
        self.vectors: Dict[str, List[float]] = {}  # file -> embedding vector
        self._cache_path = self.project_path / '.gondola_index.json'
        self._model = None  # Lazy load

    def build(self, force: bool = False) -> 'ProjectIndex':
        """Scan project and build the index. Uses cache if available."""
        if not force and self._load_cache():
            # If loaded from cache but vectors are missing and we have the capability,
            # we should still generate them.
            if HAS_EMBEDDINGS and not self.vectors:
                self._generate_embeddings()
                self._save_cache()
            return self

        self._scan_directory(self.project_path)
        if HAS_EMBEDDINGS:
            self._generate_embeddings()
        self._save_cache()
        return self

    def _should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored."""
        name = path.name
        for pattern in self.IGNORE_PATTERNS:
            if pattern.startswith('*'):
                if name.endswith(pattern[1:]):
                    return True
            elif name == pattern:
                return True
        return False

    def _scan_directory(self, directory: Path, depth: int = 0, max_depth: int = 6):
        """Recursively scan directory and index files."""
        if depth > max_depth:
            return

        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            return

        rel_dir = str(directory.relative_to(self.project_path))
        if rel_dir == '.':
            rel_dir = ''

        files_in_dir = []

        for entry in entries:
            if self._should_ignore(entry):
                continue

            if entry.is_dir():
                self._scan_directory(entry, depth + 1, max_depth)
            elif entry.is_file():
                rel_path = str(entry.relative_to(self.project_path))
                files_in_dir.append(entry.name)

                # Only analyze code files
                if entry.suffix in self.CODE_EXTENSIONS:
                    self._analyze_file(entry, rel_path)

        if files_in_dir:
            self.structure[rel_dir] = files_in_dir

    def _analyze_file(self, file_path: Path, rel_path: str):
        """Analyze a single file and extract summary, symbols, dependencies."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return

        # Store content hash for change detection
        self.file_hashes[rel_path] = hashlib.md5(content[:10000].encode()).hexdigest()[:8]

        # Generate summary based on file type and content
        self.file_summaries[rel_path] = self._generate_summary(file_path, content)

        # Extract symbols and dependencies based on file type
        suffix = file_path.suffix

        if suffix == '.py':
            self._analyze_python(rel_path, content)
        elif suffix in {'.js', '.jsx', '.ts', '.tsx'}:
            self._analyze_javascript(rel_path, content)
        elif suffix == '.html':
            self.symbols[rel_path] = {'type': 'template'}
        elif suffix == '.css':
            self.symbols[rel_path] = {'type': 'styles'}
        elif suffix == '.json':
            self.symbols[rel_path] = {'type': 'config'}

    def _generate_summary(self, file_path: Path, content: str) -> str:
        """Generate a one-line summary of what this file does."""
        name = file_path.stem
        suffix = file_path.suffix

        # Check for docstring/comment at top of file
        lines = content.split('\n')[:20]

        # Python: look for module docstring
        if suffix == '.py':
            docstring_match = re.search(r'^[\'\"]{3}(.*?)[\'\"]{3}', content, re.DOTALL)
            if docstring_match:
                doc = docstring_match.group(1).strip().split('\n')[0]
                if len(doc) < 80:
                    return doc

        # JS/TS: look for top comment
        if suffix in {'.js', '.ts', '.jsx', '.tsx'}:
            for line in lines:
                if line.strip().startswith('//'):
                    comment = line.strip()[2:].strip()
                    if len(comment) > 10 and len(comment) < 80:
                        return comment
                elif line.strip().startswith('/*'):
                    match = re.search(r'/\*\*?\s*(.*?)[\*\n]', line)
                    if match:
                        return match.group(1).strip()

        # Infer from filename patterns
        name_lower = name.lower()

        if 'test' in name_lower:
            return f"Tests for {name.replace('test_', '').replace('_test', '')}"
        if name_lower in {'index', 'main', 'app'}:
            return "Main entry point"
        if name_lower in {'config', 'settings', 'constants'}:
            return "Configuration and settings"
        if name_lower in {'utils', 'helpers', 'util'}:
            return "Utility functions"
        if name_lower in {'api', 'routes', 'endpoints'}:
            return "API endpoints"
        if name_lower in {'models', 'schema', 'types'}:
            return "Data models/types"
        if 'component' in name_lower or suffix in {'.jsx', '.tsx'}:
            return f"UI component: {name}"

        # Count what's in the file
        if suffix == '.py':
            classes = len(re.findall(r'^class\s+\w+', content, re.MULTILINE))
            funcs = len(re.findall(r'^def\s+\w+', content, re.MULTILINE))
            if classes > 0:
                return f"{classes} class(es), {funcs} function(s)"
            elif funcs > 0:
                return f"{funcs} function(s)"

        return f"{suffix[1:].upper()} file"

    def _analyze_python(self, rel_path: str, content: str):
        """Extract Python symbols and imports with line numbers."""
        symbols = {'functions': [], 'classes': []}
        imports = set()

        # Extract classes
        for match in re.finditer(r'^class\s+(\w+)', content, re.MULTILINE):
            # Calculate line number
            line_no = content.count('\n', 0, match.start()) + 1
            symbols['classes'].append({'name': match.group(1), 'line': line_no})

        # Extract top-level functions
        for match in re.finditer(r'^def\s+(\w+)', content, re.MULTILINE):
            line_no = content.count('\n', 0, match.start()) + 1
            symbols['functions'].append({'name': match.group(1), 'line': line_no})

        # Extract imports (simplified - just local imports)
        for match in re.finditer(r'^from\s+(\S+)\s+import|^import\s+(\S+)', content, re.MULTILINE):
            module = match.group(1) or match.group(2)
            if module and not module.startswith('.') and '.' not in module:
                # Could be a local module
                imports.add(module)

        self.symbols[rel_path] = symbols
        if imports:
            self.dependencies[rel_path] = imports

    def _analyze_javascript(self, rel_path: str, content: str):
        """Extract JavaScript/TypeScript symbols and imports with line numbers."""
        symbols = {'functions': [], 'classes': [], 'exports': []}
        imports = set()

        # Extract classes
        for match in re.finditer(r'class\s+(\w+)', content):
            line_no = content.count('\n', 0, match.start()) + 1
            symbols['classes'].append({'name': match.group(1), 'line': line_no})

        # Extract functions (named and arrow)
        for match in re.finditer(r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)', content):
            name = match.group(1) or match.group(2)
            if name:
                line_no = content.count('\n', 0, match.start()) + 1
                symbols['functions'].append({'name': name, 'line': line_no})

        # Extract exports
        for match in re.finditer(r'export\s+(?:default\s+)?(?:function|class|const|let|var)\s+(\w+)', content):
            line_no = content.count('\n', 0, match.start()) + 1
            symbols['exports'].append({'name': match.group(1), 'line': line_no})

        # Extract imports
        for match in re.finditer(r"(?:import|from)\s+['\"]\.?\.?/?([^'\"]+)['\"]", content):
            imp = match.group(1)
            if not imp.startswith('@') and not imp.startswith('http'):
                imports.add(imp)

        self.symbols[rel_path] = symbols
        if imports:
            self.dependencies[rel_path] = imports

    def _generate_embeddings(self):
        """Generate vector embeddings for all indexed files."""
        if not HAS_EMBEDDINGS or not self.file_summaries:
            return

        if self._model is None:
            # Use a fast, small, CPU-optimized model
            self._model = SentenceTransformer('all-MiniLM-L6-v2')

        # Only embed files that don't have vectors or have changed
        files_to_embed = []
        texts_to_embed = []

        for rel_path, summary in self.file_summaries.items():
            if rel_path not in self.vectors:
                # Combine path and summary for better conceptual matching
                text = f"file: {rel_path}\ndescription: {summary}"
                
                # Add symbols if available
                if rel_path in self.symbols:
                    syms = self.symbols[rel_path]
                    if syms.get('functions'):
                        func_names = [f['name'] if isinstance(f, dict) else f for f in syms['functions'][:10]]
                        text += f"\nfunctions: {', '.join(func_names)}"
                    if syms.get('classes'):
                        class_names = [c['name'] if isinstance(c, dict) else c for c in syms['classes'][:5]]
                        text += f"\nclasses: {', '.join(class_names)}"
                
                files_to_embed.append(rel_path)
                texts_to_embed.append(text)

        if texts_to_embed:
            embeddings = self._model.encode(texts_to_embed)
            for i, rel_path in enumerate(files_to_embed):
                self.vectors[rel_path] = embeddings[i].tolist()

    def semantic_search(self, query: str, max_results: int = 5) -> List[Tuple[str, float]]:
        """Perform semantic search using vector similarity. Falls back to keyword search if vectors unavailable."""
        if not HAS_EMBEDDINGS or not self.vectors:
            # Fallback to keyword-based relevance scoring
            results = []
            query_words = set(re.findall(r'\w+', query.lower()))
            
            for filepath, summary in self.file_summaries.items():
                score = 0.0
                filepath_lower = filepath.lower()
                summary_lower = summary.lower()
                
                # Match in filepath
                for word in query_words:
                    if word in filepath_lower:
                        score += 0.4
                    if word in summary_lower:
                        score += 0.2
                
                # Match in symbols
                if filepath in self.symbols:
                    syms = self.symbols[filepath]
                    for sym_type in ['functions', 'classes']:
                        if sym_type in syms:
                            for sym in syms[sym_type]:
                                name = sym['name'] if isinstance(sym, dict) else sym
                                if any(word in name.lower() for word in query_words):
                                    score += 0.3
                
                if score > 0:
                    # Normalize score to 0.0-1.0 range (rough estimate)
                    results.append((filepath, min(0.95, score)))
            
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:max_results]

        if self._model is None:
            self._model = SentenceTransformer('all-MiniLM-L6-v2')

        query_vector = self._model.encode([query])[0]
        
        results = []
        for rel_path, vector in self.vectors.items():
            # Cosine similarity
            similarity = np.dot(query_vector, vector) / (np.linalg.norm(query_vector) * np.linalg.norm(vector))
            results.append((rel_path, float(similarity)))
            
        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_results]

    def get_relevant_files(self, task: str, max_files: int = 5) -> List[Tuple[str, str, float]]:
        """
        Given a task description, return the most relevant files.
        Returns list of (filepath, summary, relevance_score) tuples.
        Uses hybrid scoring (Keywords + Vector Similarity).
        """
        task_lower = task.lower()
        scores = {}

        # 1. Keyword-based scoring (High precision)
        for filepath, summary in self.file_summaries.items():
            score = 0.0
            filepath_lower = filepath.lower()
            summary_lower = summary.lower()

            # Check task keywords
            for category, keywords in self.TASK_KEYWORDS.items():
                if any(kw in task_lower for kw in keywords):
                    if any(kw in filepath_lower or kw in summary_lower for kw in keywords):
                        score += 3.0

            # Direct word matches in filepath
            task_words = set(re.findall(r'\w+', task_lower))
            path_words = set(re.findall(r'\w+', filepath_lower))
            matches = task_words & path_words
            score += len(matches) * 2.0

            # Matches in summary
            summary_words = set(re.findall(r'\w+', summary_lower))
            summary_matches = task_words & summary_words
            score += len(summary_matches) * 1.0

            # Symbol matches
            if filepath in self.symbols:
                syms = self.symbols[filepath]
                for sym_type in ['functions', 'classes', 'exports']:
                    if sym_type in syms:
                        for sym in syms[sym_type]:
                            # sym can be a dict {'name': '...', 'line': ...} or a string
                            name = sym['name'] if isinstance(sym, dict) else sym
                            if any(word in name.lower() for word in task_words):
                                score += 1.5

            if score > 0:
                scores[filepath] = score

        # 2. Semantic scoring (High recall)
        if HAS_EMBEDDINGS and self.vectors:
            semantic_results = self.semantic_search(task, max_results=max_files * 2)
            for filepath, similarity in semantic_results:
                # Scale semantic similarity to be competitive with keyword scores
                # Similarity is usually 0.3-0.8 for good matches
                semantic_boost = similarity * 5.0
                scores[filepath] = scores.get(filepath, 0.0) + semantic_boost

        # Sort by score and return top results
        sorted_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            (filepath, self.file_summaries.get(filepath, ''), score)
            for filepath, score in sorted_files[:max_files]
        ]

    def to_prompt(self, max_tokens: int = 1500) -> str:
        """
        Generate a compact project overview for the system prompt.
        Fits within specified token limit (rough estimate: 4 chars = 1 token).
        """
        lines = ["## Project Structure\n"]

        # Build tree-like structure
        char_count = 50
        max_chars = max_tokens * 4

        # Group files by directory
        for directory in sorted(self.structure.keys()):
            if char_count > max_chars:
                lines.append("... (more files)")
                break

            dir_display = directory if directory else "(root)"
            dir_line = f"\n**{dir_display}/**\n"
            char_count += len(dir_line)
            lines.append(dir_line)

            for filename in self.structure[directory][:10]:  # Max 10 files per dir
                filepath = f"{directory}/{filename}" if directory else filename
                summary = self.file_summaries.get(filepath, '')

                if summary:
                    file_line = f"- `{filename}` - {summary}\n"
                else:
                    file_line = f"- `{filename}`\n"

                if char_count + len(file_line) > max_chars:
                    break

                char_count += len(file_line)
                lines.append(file_line)

            if len(self.structure[directory]) > 10:
                lines.append(f"  ... +{len(self.structure[directory]) - 10} more files\n")

        return ''.join(lines)

    def get_context_for_task(self, task: str, max_tokens: int = 3000) -> str:
        """
        Build context for a specific task.
        Includes project overview + relevant file details.
        """
        lines = []

        # Start with compact overview
        overview = self.to_prompt(max_tokens=800)
        lines.append(overview)

        # Add relevant files with more detail
        relevant = self.get_relevant_files(task, max_files=5)

        if relevant:
            lines.append("\n## Files Relevant to Your Task\n")
            for filepath, summary, score in relevant:
                lines.append(f"\n**{filepath}** (relevance: {score:.1f})")
                if summary:
                    lines.append(f"\n  Summary: {summary}")

                # Add symbols if available
                if filepath in self.symbols:
                    syms = self.symbols[filepath]
                    if syms.get('classes'):
                        class_names = [f"{c['name']} (line {c['line']})" if isinstance(c, dict) else c for c in syms['classes'][:5]]
                        lines.append(f"\n  Classes: {', '.join(class_names)}")
                    if syms.get('functions'):
                        funcs = syms['functions'][:8]
                        func_names = [f"{f['name']} (line {f['line']})" if isinstance(f, dict) else f for f in funcs]
                        lines.append(f"\n  Functions: {', '.join(func_names)}")
                    if syms.get('exports'):
                        export_names = [e['name'] if isinstance(e, dict) else e for e in syms['exports'][:5]]
                        lines.append(f"\n  Exports: {', '.join(export_names)}")
                lines.append("\n")

        return ''.join(lines)

    def _load_cache(self) -> bool:
        """Load cached index if it exists and is valid."""
        if not self._cache_path.exists():
            return False

        try:
            cache = json.loads(self._cache_path.read_text())

            # Quick validation: check a few random files still exist
            sample_files = list(cache.get('file_summaries', {}).keys())[:5]
            for f in sample_files:
                if not (self.project_path / f).exists():
                    return False

            self.structure = cache.get('structure', {})
            self.file_summaries = cache.get('file_summaries', {})
            self.symbols = cache.get('symbols', {})
            self.dependencies = {k: set(v) for k, v in cache.get('dependencies', {}).items()}
            self.file_hashes = cache.get('file_hashes', {})
            self.vectors = cache.get('vectors', {})
            return True
        except Exception:
            return False

    def _save_cache(self):
        """Save index to cache file."""
        try:
            cache = {
                'structure': self.structure,
                'file_summaries': self.file_summaries,
                'symbols': self.symbols,
                'dependencies': {k: list(v) for k, v in self.dependencies.items()},
                'file_hashes': self.file_hashes,
                'vectors': self.vectors
            }
            self._cache_path.write_text(json.dumps(cache, indent=2))
        except Exception:
            pass  # Cache is optional

    def invalidate_file(self, filepath: str):
        """Mark a file as needing re-analysis."""
        if filepath in self.file_hashes:
            del self.file_hashes[filepath]
        if filepath in self.vectors:
            del self.vectors[filepath]

    def file_count(self) -> int:
        """Return total number of indexed files."""
        return len(self.file_summaries)

    def add_manual_knowledge(self, key: str, content: str):
        """Add manual knowledge to the index."""
        if not hasattr(self, 'manual_knowledge'):
            self.manual_knowledge = {}
        self.manual_knowledge[key] = content
        self._save_cache()

    def __repr__(self):
        return f"ProjectIndex({self.project_path}, {self.file_count()} files)"
