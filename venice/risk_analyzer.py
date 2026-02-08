import re
import hashlib
import os

MODEL_RISK_TOLERANCE = {
    "claude-opus": 120,      # Highest tolerance - rarely blocks
    "claude-sonnet": 100,    # Standard threshold
    "glm": 120,              # High tolerance for GLM-4
    "qwen": 90,              # Slightly more cautious (can be overconfident)
    "llama": 80,             # More cautious (sometimes guesses)
    "meta-maverick": 80,     # Same as Llama
    "maverick": 80,
    "groq": 70,              # Most cautious (fast but less accurate)
}

def get_block_threshold(model_id: str) -> int:
    for key, threshold in MODEL_RISK_TOLERANCE.items():
        if key in model_id.lower():
            return threshold
    return 100  # Default

class RiskAnalyzer:
    """Pre-flight risk analyzer for code edits."""
    
    def score_edit(self, file_path: str, search_block: str, replace_block: str, agent_state, model_id: str = None) -> dict:
        risk_score = 0
        flags = []
        
        # RISK 1: Large deletions
        search_lines = len(search_block.strip().split('\n'))
        replace_lines = len(replace_block.strip().split('\n'))
        net_deletion = search_lines - replace_lines
        
        if net_deletion > 20:
            risk_score += 50
            flags.append(f"DELETES {net_deletion} lines")
        elif net_deletion > 10:
            risk_score += 25
            flags.append(f"Deletes {net_deletion} lines")
            
        # RISK 2: File not recently read
        last_read_turn = agent_state.get_last_read_turn(file_path)
        current_turn = agent_state.turn_count
        
        if last_read_turn is None:
            risk_score += 100  # CRITICAL: Never read this file
            flags.append("FILE NEVER READ")
        elif (current_turn - last_read_turn) > 5:
            risk_score += 40
            flags.append(f"File last read {current_turn - last_read_turn} turns ago")
            
        # RISK 3: Signature changes (function definitions)
        if re.search(r'^\s*def \w+\(', search_block, re.MULTILINE):
            search_sigs = re.findall(r'def (\w+)\(.*\)', search_block)
            replace_sigs = re.findall(r'def (\w+)\(.*\)', replace_block)
            
            if search_sigs != replace_sigs:
                risk_score += 60
                flags.append(f"CHANGES FUNCTION SIGNATURE: {search_sigs} → {replace_sigs}")
                
        # RISK 4: Class definition changes
        if re.search(r'^\s*class \w+', search_block, re.MULTILINE):
            risk_score += 30
            flags.append("Modifies class definition")
            
        # RISK 5: Import statement changes
        if 'import ' in search_block or 'from ' in search_block:
            risk_score += 20
            flags.append("Modifies imports")
            
        # RISK 6: File was externally modified
        # Note: We pass None for current_hash if we don't have it; 
        # FileOpsMixin typically mocks this method with the actual hash before calling.
        try:
            if agent_state.file_modified_externally(file_path, None):
                risk_score += 80
                flags.append("FILE MODIFIED EXTERNALLY SINCE LAST READ")
        except TypeError:
            # Fallback for older versions of AgentState or if mocked improperly
            pass
            
        # RISK 7: Touching critical files
        critical_patterns = ['__init__.py', 'config', 'settings', 'main.py']
        if any(pattern in file_path.lower() for pattern in critical_patterns):
            risk_score += 15
            flags.append("Critical system file")
            
        block_threshold = get_block_threshold(model_id) if model_id else 100

        return {
            "risk_score": risk_score,
            "risk_level": self._get_risk_level(risk_score),
            "flags": flags,
            "requires_verification": risk_score >= block_threshold,
            "block_threshold": block_threshold
        }
    
    def _get_risk_level(self, score: int) -> str:
        if score >= 100:
            return "CRITICAL"
        elif score >= 50:
            return "HIGH"
        elif score >= 25:
            return "MEDIUM"
        else:
            return "LOW"