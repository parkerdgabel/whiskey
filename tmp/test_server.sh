#!/bin/bash

echo "Testing Whiskey ASGI Server"
echo "=========================="

echo -e "\n1. Testing root endpoint:"
curl -s http://localhost:8000/ | jq .

echo -e "\n2. Testing health endpoint:"
curl -s http://localhost:8000/health | jq .

echo -e "\n3. Testing greeting endpoint:"
curl -s http://localhost:8000/greet/World | jq .

echo -e "\n4. Testing counter (initial):"
curl -s http://localhost:8000/count | jq .

echo -e "\n5. Incrementing counter:"
curl -s -X POST http://localhost:8000/count/increment | jq .

echo -e "\n6. Testing counter (after increment):"
curl -s http://localhost:8000/count | jq .

echo -e "\n7. Testing echo endpoint:"
curl -s -X POST http://localhost:8000/echo \
  -H "Content-Type: application/json" \
  -d '{"test": "data", "number": 42}' | jq .

echo -e "\n8. Testing 404 error:"
curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:8000/does-not-exist

echo -e "\nAll tests completed!"