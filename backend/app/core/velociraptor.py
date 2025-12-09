"""
Velociraptor API Client

This module provides integration with Velociraptor servers for artifact
collection, hunt management, and client operations.
"""

from typing import List, Dict, Any, Optional
import httpx
from datetime import datetime


class VelociraptorClient:
    """Client for interacting with Velociraptor API"""
    
    def __init__(self, base_url: str, api_key: str):
        """
        Initialize Velociraptor client
        
        Args:
            base_url: Base URL of Velociraptor server
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "Authorization": f"******",
            "Content-Type": "application/json"
        }
    
    async def list_clients(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List all clients
        
        Args:
            limit: Maximum number of clients to return
        
        Returns:
            List of client information dictionaries
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/clients",
                headers=self.headers,
                params={"count": limit}
            )
            response.raise_for_status()
            return response.json()
    
    async def get_client(self, client_id: str) -> Dict[str, Any]:
        """
        Get information about a specific client
        
        Args:
            client_id: Client ID
        
        Returns:
            Client information dictionary
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/clients/{client_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def collect_artifact(
        self,
        client_id: str,
        artifact_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Collect an artifact from a client
        
        Args:
            client_id: Client ID
            artifact_name: Name of artifact to collect
            parameters: Optional parameters for artifact collection
        
        Returns:
            Collection flow information
        """
        payload = {
            "client_id": client_id,
            "artifacts": [artifact_name],
            "parameters": parameters or {}
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/flows",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
    
    async def create_hunt(
        self,
        hunt_name: str,
        artifact_name: str,
        description: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new hunt
        
        Args:
            hunt_name: Name of the hunt
            artifact_name: Artifact to collect
            description: Hunt description
            parameters: Optional parameters for artifact
        
        Returns:
            Hunt information
        """
        payload = {
            "hunt_name": hunt_name,
            "description": description,
            "artifacts": [artifact_name],
            "parameters": parameters or {}
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/hunts",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
    
    async def get_hunt_results(
        self,
        hunt_id: str,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get results from a hunt
        
        Args:
            hunt_id: Hunt ID
            limit: Maximum number of results to return
        
        Returns:
            List of hunt results
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/hunts/{hunt_id}/results",
                headers=self.headers,
                params={"count": limit}
            )
            response.raise_for_status()
            return response.json()
    
    async def get_flow_results(
        self,
        client_id: str,
        flow_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get results from a flow
        
        Args:
            client_id: Client ID
            flow_id: Flow ID
        
        Returns:
            List of flow results
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/clients/{client_id}/flows/{flow_id}/results",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()


def get_velociraptor_client(base_url: str, api_key: str) -> VelociraptorClient:
    """
    Factory function to create Velociraptor client
    
    Args:
        base_url: Base URL of Velociraptor server
        api_key: API key for authentication
    
    Returns:
        Configured VelociraptorClient instance
    """
    return VelociraptorClient(base_url, api_key)
