"""Test RAG pipeline components in isolation."""
import asyncio
import sys

# Add the app directory to the path
sys.path.insert(0, 'c:\\Users\\ze9167523\\IdeaProjects\\doctel')

async def test_embedding():
    """Test embedding generation."""
    print("=== Testing embedding generation ===")
    from app.db.database import AsyncSessionLocal
    from app.services.embedding_service import generate_embedding
    
    async with AsyncSessionLocal() as db:
        embedding = await generate_embedding(db, "What does the Dunning Manual say about overdue accounts?")
        print(f"Embedding generated: length={len(embedding)}")
        return embedding

async def test_chroma_query(embedding):
    """Test ChromaDB query."""
    print("\n=== Testing ChromaDB query ===")
    from app.utils.chroma_client import chroma
    
    result = chroma.query("3", embedding, top_k=6, where=None)
    print(f"ChromaDB result keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
    docs = (result.get("documents") or [[]])[0] if isinstance(result, dict) else []
    print(f"Documents returned: {len(docs)}")
    return result

async def test_ollama():
    """Test Ollama generation."""
    print("\n=== Testing Ollama generation ===")
    from app.utils.ollama_client import ollama
    
    try:
        response = await asyncio.wait_for(
            ollama.generate("qwen3:4b", "Hello, are you working?", system="You are a helpful assistant."),
            timeout=30.0
        )
        print(f"Ollama response: {response[:100]}..." if len(response) > 100 else f"Ollama response: {response}")
        return response
    except asyncio.TimeoutError:
        print("Ollama generation TIMED OUT")
        return None
    except Exception as e:
        print(f"Ollama generation ERROR: {e}")
        return None

async def main():
    print("Starting RAG component tests...\n")
    
    # Test 1: Embedding
    try:
        embedding = await asyncio.wait_for(test_embedding(), timeout=30.0)
    except Exception as e:
        print(f"Embedding test FAILED: {e}")
        return
    
    # Test 2: ChromaDB query
    try:
        result = await asyncio.wait_for(test_chroma_query(embedding), timeout=30.0)
    except Exception as e:
        print(f"ChromaDB test FAILED: {e}")
        return
    
    # Test 3: Ollama generation
    try:
        await asyncio.wait_for(test_ollama(), timeout=60.0)
    except Exception as e:
        print(f"Ollama test FAILED: {e}")
        return
    
    print("\n=== All tests completed ===")

if __name__ == "__main__":
    asyncio.run(main())
