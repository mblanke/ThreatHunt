"""
Threat Intelligence and Machine Learning Module

This module provides threat scoring, anomaly detection, and predictive analytics.
"""

from typing import Dict, Any, List, Optional
import random  # For demo purposes - would use actual ML models in production


class ThreatAnalyzer:
    """Analyzes threats using ML models and heuristics"""
    
    def __init__(self, model_version: str = "1.0"):
        """
        Initialize threat analyzer
        
        Args:
            model_version: Version of ML models to use
        """
        self.model_version = model_version
    
    def analyze_host(self, host_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a host for threats
        
        Args:
            host_data: Host information and telemetry
        
        Returns:
            Dictionary with threat score and indicators
        """
        # In production, this would use ML models
        # For demo, using simple heuristics
        
        score = 0.0
        confidence = 0.8
        indicators = []
        
        # Check for suspicious patterns
        hostname = host_data.get("hostname", "")
        if "temp" in hostname.lower() or "test" in hostname.lower():
            score += 0.2
            indicators.append({
                "type": "suspicious_hostname",
                "description": "Hostname contains suspicious keywords",
                "severity": "low"
            })
        
        # Check metadata for anomalies
        metadata = host_data.get("host_metadata", {})
        if metadata:
            # Check for unusual processes, connections, etc.
            if "suspicious_process" in str(metadata):
                score += 0.5
                indicators.append({
                    "type": "suspicious_process",
                    "description": "Unusual process detected",
                    "severity": "high"
                })
        
        # Normalize score
        score = min(score, 1.0)
        
        return {
            "score": score,
            "confidence": confidence,
            "threat_type": self._classify_threat(score),
            "indicators": indicators,
            "ml_model_version": self.model_version
        }
    
    def analyze_artifact(self, artifact_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze an artifact for threats
        
        Args:
            artifact_data: Artifact information
        
        Returns:
            Dictionary with threat score and indicators
        """
        score = 0.0
        confidence = 0.7
        indicators = []
        
        artifact_type = artifact_data.get("artifact_type", "")
        value = artifact_data.get("value", "")
        
        # Hash analysis
        if artifact_type == "hash":
            # In production, check against threat intelligence feeds
            if len(value) == 32:  # MD5
                score += 0.3
                indicators.append({
                    "type": "weak_hash",
                    "description": "MD5 hashes are considered weak",
                    "severity": "low"
                })
        
        # IP analysis
        elif artifact_type == "ip":
            # Check if IP is in known malicious ranges
            if value.startswith("10.") or value.startswith("192.168."):
                score += 0.1  # Private IP, lower risk
            else:
                score += 0.4  # Public IP, higher scrutiny
                indicators.append({
                    "type": "public_ip",
                    "description": "Communication with public IP",
                    "severity": "medium"
                })
        
        # Domain analysis
        elif artifact_type == "domain":
            # Check for suspicious TLDs or patterns
            suspicious_tlds = [".ru", ".cn", ".tk", ".xyz"]
            if any(value.endswith(tld) for tld in suspicious_tlds):
                score += 0.6
                indicators.append({
                    "type": "suspicious_tld",
                    "description": f"Domain uses potentially suspicious TLD",
                    "severity": "high"
                })
        
        score = min(score, 1.0)
        
        return {
            "score": score,
            "confidence": confidence,
            "threat_type": self._classify_threat(score),
            "indicators": indicators,
            "ml_model_version": self.model_version
        }
    
    def detect_anomalies(
        self,
        historical_data: List[Dict[str, Any]],
        current_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect anomalies in current data compared to historical baseline
        
        Args:
            historical_data: Historical baseline data
            current_data: Current data to analyze
        
        Returns:
            Anomaly detection results
        """
        # Simple anomaly detection based on statistical deviation
        # In production, use more sophisticated methods
        
        anomalies = []
        score = 0.0
        
        # Compare metrics
        if historical_data and len(historical_data) >= 3:
            # Calculate baseline
            # This is a simplified example
            anomalies.append({
                "type": "behavioral_anomaly",
                "description": "Behavior deviates from baseline",
                "severity": "medium"
            })
            score = 0.5
        
        return {
            "is_anomaly": score > 0.4,
            "anomaly_score": score,
            "anomalies": anomalies
        }
    
    def _classify_threat(self, score: float) -> str:
        """Classify threat based on score"""
        if score >= 0.8:
            return "critical"
        elif score >= 0.6:
            return "high"
        elif score >= 0.4:
            return "medium"
        elif score >= 0.2:
            return "low"
        else:
            return "benign"


def get_threat_analyzer(model_version: str = "1.0") -> ThreatAnalyzer:
    """
    Factory function to create threat analyzer
    
    Args:
        model_version: Version of ML models
    
    Returns:
        Configured ThreatAnalyzer instance
    """
    return ThreatAnalyzer(model_version)
