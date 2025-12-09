#!/bin/bash

# Test script for VelociCompanion API
# This script demonstrates the authentication flow and basic API usage

API_URL="http://localhost:8000"

echo "==================================="
echo "VelociCompanion API Test Script"
echo "==================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Health Check
echo -e "${YELLOW}1. Testing health endpoint...${NC}"
response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health")
if [ "$response" = "200" ]; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed (HTTP $response)${NC}"
    exit 1
fi
echo ""

# Test 2: Register a new user
echo -e "${YELLOW}2. Registering a new user...${NC}"
register_response=$(curl -s -X POST "$API_URL/api/auth/register" \
    -H "Content-Type: application/json" \
    -d '{
        "username": "testuser",
        "password": "testpass123",
        "role": "user"
    }')

if echo "$register_response" | grep -q "username"; then
    echo -e "${GREEN}✓ User registration successful${NC}"
    echo "Response: $register_response"
else
    echo -e "${YELLOW}⚠ User might already exist or registration failed${NC}"
    echo "Response: $register_response"
fi
echo ""

# Test 3: Login
echo -e "${YELLOW}3. Logging in...${NC}"
login_response=$(curl -s -X POST "$API_URL/api/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=testuser&password=testpass123")

TOKEN=$(echo "$login_response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -n "$TOKEN" ]; then
    echo -e "${GREEN}✓ Login successful${NC}"
    echo "Token: ${TOKEN:0:20}..."
else
    echo -e "${RED}✗ Login failed${NC}"
    echo "Response: $login_response"
    exit 1
fi
echo ""

# Test 4: Get current user profile
echo -e "${YELLOW}4. Getting current user profile...${NC}"
profile_response=$(curl -s -X GET "$API_URL/api/auth/me" \
    -H "Authorization: Bearer $TOKEN")

if echo "$profile_response" | grep -q "username"; then
    echo -e "${GREEN}✓ Profile retrieval successful${NC}"
    echo "Profile: $profile_response"
else
    echo -e "${RED}✗ Profile retrieval failed${NC}"
    echo "Response: $profile_response"
fi
echo ""

# Test 5: List tenants
echo -e "${YELLOW}5. Listing tenants...${NC}"
tenants_response=$(curl -s -X GET "$API_URL/api/tenants" \
    -H "Authorization: Bearer $TOKEN")

if echo "$tenants_response" | grep -q "name"; then
    echo -e "${GREEN}✓ Tenants list retrieved${NC}"
    echo "Tenants: $tenants_response"
else
    echo -e "${YELLOW}⚠ No tenants found or access denied${NC}"
    echo "Response: $tenants_response"
fi
echo ""

# Test 6: List hosts
echo -e "${YELLOW}6. Listing hosts...${NC}"
hosts_response=$(curl -s -X GET "$API_URL/api/hosts" \
    -H "Authorization: Bearer $TOKEN")

echo "Hosts: $hosts_response"
echo ""

# Test 7: Test authentication protection (without token)
echo -e "${YELLOW}7. Testing authentication protection...${NC}"
unauth_response=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_URL/api/hosts")

if [ "$unauth_response" = "401" ]; then
    echo -e "${GREEN}✓ Authentication protection working (got 401 as expected)${NC}"
else
    echo -e "${RED}✗ Authentication not properly enforced (got HTTP $unauth_response)${NC}"
fi
echo ""

echo "==================================="
echo -e "${GREEN}API Testing Complete!${NC}"
echo "==================================="
