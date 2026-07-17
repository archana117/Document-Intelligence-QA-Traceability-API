import hashlib

class ContentHasher:
    @staticmethod
    def compute_hash(heading: str, body: str) -> str:
        """
        Computes SHA256 hash of the node's heading and body text.
        Consistent whitespace handling is enforced to avoid false mismatches.
        """
        clean_heading = " ".join(heading.strip().split())
        clean_body = " ".join(body.strip().split())
        
        content = f"{clean_heading}\n{clean_body}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
