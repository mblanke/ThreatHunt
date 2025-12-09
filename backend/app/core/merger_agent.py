"""
Merger Agent

Combines and synthesizes results from multiple LLM models.
"""

from typing import Dict, Any, List, Optional
from enum import Enum


class MergeStrategy(Enum):
    """Strategies for merging LLM results"""
    CONSENSUS = "consensus"  # Take majority vote
    WEIGHTED = "weighted"  # Weight by model confidence
    CONCATENATE = "concatenate"  # Combine all outputs
    BEST_QUALITY = "best_quality"  # Select highest quality response
    ENSEMBLE = "ensemble"  # Ensemble multiple results


class MergerAgent:
    """
    Merger Agent - Combines results from multiple LLM executions
    
    When multiple models process the same or related requests,
    this agent intelligently merges their outputs into a coherent response.
    """
    
    def __init__(self, default_strategy: MergeStrategy = MergeStrategy.CONSENSUS):
        """
        Initialize merger agent
        
        Args:
            default_strategy: Default merging strategy
        """
        self.default_strategy = default_strategy
    
    def merge_results(
        self,
        results: List[Dict[str, Any]],
        strategy: Optional[MergeStrategy] = None
    ) -> Dict[str, Any]:
        """
        Merge multiple LLM results using specified strategy
        
        Args:
            results: List of results from different models
            strategy: Merging strategy (uses default if not specified)
        
        Returns:
            Merged result
        """
        if not results:
            return {"error": "No results to merge"}
        
        if len(results) == 1:
            return results[0]
        
        merge_strategy = strategy or self.default_strategy
        
        if merge_strategy == MergeStrategy.CONSENSUS:
            return self._merge_consensus(results)
        elif merge_strategy == MergeStrategy.WEIGHTED:
            return self._merge_weighted(results)
        elif merge_strategy == MergeStrategy.CONCATENATE:
            return self._merge_concatenate(results)
        elif merge_strategy == MergeStrategy.BEST_QUALITY:
            return self._merge_best_quality(results)
        elif merge_strategy == MergeStrategy.ENSEMBLE:
            return self._merge_ensemble(results)
        else:
            return self._merge_consensus(results)
    
    def _merge_consensus(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge by consensus - take majority vote or most common response
        
        Args:
            results: List of results
        
        Returns:
            Consensus result
        """
        # For classification tasks, take majority vote
        if all("classification" in r for r in results):
            classifications = [r["classification"] for r in results]
            most_common = max(set(classifications), key=classifications.count)
            
            return {
                "strategy": "consensus",
                "result": most_common,
                "confidence": classifications.count(most_common) / len(classifications),
                "votes": dict((k, classifications.count(k)) for k in set(classifications))
            }
        
        # For text generation, use first high-quality result
        valid_results = [r for r in results if "response" in r and r["response"]]
        if valid_results:
            return {
                "strategy": "consensus",
                "result": valid_results[0]["response"],
                "num_models": len(results)
            }
        
        return {"strategy": "consensus", "result": None}
    
    def _merge_weighted(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge by weighted average based on model confidence
        
        Args:
            results: List of results with confidence scores
        
        Returns:
            Weighted result
        """
        # Extract results with confidence scores
        weighted_results = [
            (r.get("response", ""), r.get("confidence", 0.5))
            for r in results
        ]
        
        # Sort by confidence
        weighted_results.sort(key=lambda x: x[1], reverse=True)
        
        return {
            "strategy": "weighted",
            "result": weighted_results[0][0],
            "confidence": weighted_results[0][1],
            "all_results": [
                {"response": resp, "confidence": conf}
                for resp, conf in weighted_results
            ]
        }
    
    def _merge_concatenate(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Concatenate all results
        
        Args:
            results: List of results
        
        Returns:
            Concatenated result
        """
        responses = [
            r.get("response", "") for r in results if r.get("response")
        ]
        
        return {
            "strategy": "concatenate",
            "result": "\n\n---\n\n".join(responses),
            "num_responses": len(responses)
        }
    
    def _merge_best_quality(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Select the highest quality response
        
        Args:
            results: List of results
        
        Returns:
            Best quality result
        """
        # Score responses by length and presence of key indicators
        scored_results = []
        
        for r in results:
            response = r.get("response", "")
            if not response:
                continue
            
            score = 0
            score += len(response) / 100  # Longer responses get higher score
            score += response.count(".") * 0.5  # More complete sentences
            score += response.count("\n") * 0.3  # Better formatting
            
            scored_results.append((response, score, r))
        
        if not scored_results:
            return {"strategy": "best_quality", "result": None}
        
        scored_results.sort(key=lambda x: x[1], reverse=True)
        best_response, best_score, best_result = scored_results[0]
        
        return {
            "strategy": "best_quality",
            "result": best_response,
            "quality_score": best_score,
            "model": best_result.get("model", "unknown")
        }
    
    def _merge_ensemble(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Ensemble multiple results by combining their insights
        
        Args:
            results: List of results
        
        Returns:
            Ensemble result
        """
        # Collect unique insights from all models
        all_responses = [r.get("response", "") for r in results if r.get("response")]
        
        # Create ensemble summary
        ensemble_summary = {
            "strategy": "ensemble",
            "num_models": len(results),
            "individual_results": [
                {
                    "model": r.get("model", "unknown"),
                    "response": r.get("response", ""),
                    "confidence": r.get("confidence", 0.5)
                }
                for r in results
            ],
            "synthesized_result": self._synthesize_insights(all_responses)
        }
        
        return ensemble_summary
    
    def _synthesize_insights(self, responses: List[str]) -> str:
        """
        Synthesize insights from multiple responses
        
        Args:
            responses: List of response strings
        
        Returns:
            Synthesized summary
        """
        if not responses:
            return ""
        
        # Simple synthesis - in production, use another LLM to synthesize
        unique_points = []
        for response in responses:
            sentences = response.split(". ")
            for sentence in sentences:
                if sentence and sentence not in unique_points:
                    unique_points.append(sentence)
        
        return ". ".join(unique_points[:10])  # Top 10 insights


def get_merger_agent(
    default_strategy: MergeStrategy = MergeStrategy.CONSENSUS
) -> MergerAgent:
    """
    Factory function to create merger agent
    
    Args:
        default_strategy: Default merging strategy
    
    Returns:
        Configured MergerAgent instance
    """
    return MergerAgent(default_strategy)
