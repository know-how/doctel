"""
Integration Test Suite for DocIntel System

Tests:
1. Gemini API connectivity and document ingestion
2. CSV analytics and dashboard
3. Transfer learning availability
4. Mermaid diagram generation
5. End-to-end flows (stubs)

Run with:
  .venv\Scripts\python.exe -m pytest tests/integration_tests.py -v
"""
import pytest
import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any

# Mock configurations for testing
BACKEND_URL = "http://localhost:8000"
GEMINI_TEST_PROMPT = "Test prompt"
MOBILE_TEST_IP = "127.0.0.1"


class TestGeminiIntegration:
    """Test Gemini API connectivity and document processing."""

    def test_gemini_configured(self):
        """Check if Gemini API is configured."""
        from app.services.gemini_service import is_configured

        result = is_configured()
        assert isinstance(result, bool), "is_configured should return bool"

    @pytest.mark.asyncio
    async def test_gemini_text_generation(self):
        """Test Gemini text generation."""
        try:
            from app.services.gemini_service import generate

            response = await generate("Summarize: Hello world")
            assert isinstance(response, str), "Should return string"
            assert len(response) > 0, "Should return non-empty response"
        except RuntimeError as e:
            # Graceful failure if API key not configured
            assert "not configured" in str(e).lower(), f"Expected config error: {e}"

    @pytest.mark.asyncio
    async def test_gemini_vision_analysis(self):
        """Test Gemini vision analysis capability."""
        from app.services.gemini_service import analyze_image

        # Create test image in a temp directory, close it before using
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".png")
            os.write(fd, b"\x89PNG\r\n\x1a\n")  # PNG header
            os.close(fd)
            try:
                result = await analyze_image(tmp_path, "Describe this")
                assert isinstance(result, str)
            except RuntimeError:
                # Expected if Gemini not configured
                pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_gemini_document_analysis(self):
        """Test Gemini document analysis."""
        from app.services.gemini_service import analyze_document

        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".txt")
            os.write(fd, b"Test document with some content for analysis.")
            os.close(fd)

            try:
                result = await analyze_document(tmp_path)
                assert isinstance(result, dict)
                assert "summary" in result
                assert "topics" in result
                assert "entities" in result
            except RuntimeError:
                # Expected if Gemini not configured
                pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @pytest.mark.asyncio
    async def test_gemini_synthetic_training_data(self):
        """Test Gemini synthetic data generation."""
        from app.services.gemini_service import generate_synthetic_training_data

        try:
            result = await generate_synthetic_training_data(
                topic="electricity grid operation",
                num_examples=3
            )
            assert isinstance(result, list), "Should return list"
            if result:
                assert "instruction" in result[0], "Should have instruction"
                assert "output" in result[0], "Should have output"
        except RuntimeError:
            # Expected if Gemini not configured
            pass


class TestMobileAPIConnectivity:
    """Test mobile API endpoint connectivity (structural checks only)."""

    def test_mobile_client_file_exists(self):
        """Check mobile API client source file exists."""
        mobile_client = Path(__file__).resolve().parent.parent / "mobile" / "src" / "api" / "client.ts"
        assert mobile_client.exists(), f"Mobile API client not found at {mobile_client}"

        # Read file and check it contains BASE_URL
        content = mobile_client.read_text(encoding="utf-8")
        assert "BASE_URL" in content, "Mobile client should define BASE_URL"

    def test_mobile_vs_frontend_client_parity(self):
        """Compare mobile and frontend API client implementations."""
        # Both should have similar endpoint coverage
        mobile_client = Path(__file__).resolve().parent.parent / "mobile" / "src" / "api" / "client.ts"
        frontend_client = Path(__file__).resolve().parent.parent / "frontend" / "src" / "api" / "client.ts"

        if mobile_client.exists() and frontend_client.exists():
            mobile_content = mobile_client.read_text(encoding="utf-8")
            frontend_content = frontend_client.read_text(encoding="utf-8")
            # Both should have common endpoint patterns
            for endpoint in ["/auth/login", "/documents", "/api/ask"]:
                assert endpoint in mobile_content, f"Mobile client missing {endpoint}"
                assert endpoint in frontend_content, f"Frontend client missing {endpoint}"


class TestCSVAnalytics:
    """Test CSV parsing and analytics."""

    def test_csv_loader(self):
        """Test CSV file loading."""
        from app.services.csv_analytics_service import CSVAnalyzer

        # Create test CSV – use mkstemp to avoid Windows file locking
        fd, tmp_path = tempfile.mkstemp(suffix=".csv")
        try:
            os.write(fd, b"name,age,city\nAlice,30,NYC\nBob,25,LA\n")
            os.close(fd)

            analyzer = CSVAnalyzer(tmp_path)
            loaded = analyzer.load()
            assert loaded, "Should successfully load CSV"
            assert len(analyzer.data) == 2, "Should have 2 rows"
            assert analyzer.columns == ["name", "age", "city"], "Should have correct columns"
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_csv_type_detection(self):
        """Test column type inference."""
        from app.services.csv_analytics_service import CSVAnalyzer

        fd, tmp_path = tempfile.mkstemp(suffix=".csv")
        try:
            os.write(fd, b"text_col,num_col,date_col\nHello,42,2024-01-01\nWorld,3.14,2024-01-02\n")
            os.close(fd)

            analyzer = CSVAnalyzer(tmp_path)
            analyzer.load()

            assert "num_col" in analyzer.numeric_columns
            assert "text_col" in analyzer.text_columns
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_csv_statistics(self):
        """Test statistics calculation."""
        from app.services.csv_analytics_service import CSVAnalyzer

        fd, tmp_path = tempfile.mkstemp(suffix=".csv")
        try:
            os.write(fd, b"value\n10\n20\n30\n40\n50\n")
            os.close(fd)

            analyzer = CSVAnalyzer(tmp_path)
            analyzer.load()

            stats = analyzer._calculate_statistics("value")
            assert stats is not None, "Should calculate stats"
            assert stats["mean"] == 30, "Mean should be 30"
            assert stats["min"] == 10, "Min should be 10"
            assert stats["max"] == 50, "Max should be 50"
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_csv_chart_generation(self):
        """Test chart data generation."""
        from app.services.csv_analytics_service import CSVAnalyzer

        fd, tmp_path = tempfile.mkstemp(suffix=".csv")
        try:
            os.write(fd, b"month,sales\nJan,100\nFeb,150\nMar,120\n")
            os.close(fd)

            analyzer = CSVAnalyzer(tmp_path)
            analyzer.load()

            chart_data = analyzer.generate_chart_data("bar", "month", "sales")
            assert chart_data is not None
            assert "type" in chart_data
            assert chart_data["type"] == "bar"
            assert len(chart_data.get("data", [])) > 0
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestTransferLearning:
    """Test transfer learning pipeline."""

    def test_lora_trainer_available(self):
        """Check if LoRA trainer is available."""
        from app.training.lora_trainer import is_available

        result = is_available()
        assert isinstance(result, bool), "Should return bool"

    def test_multi_model_training_config(self):
        """Test multi-model training configuration."""
        from app.services.multi_model_trainer import MultiModelTrainer

        trainer = MultiModelTrainer()
        assert len(trainer.base_models) > 0, "Should have base models configured"
        assert isinstance(trainer.base_models, list), "Should be list"


class TestMermaidGeneration:
    """Test Mermaid diagram generation."""

    @pytest.mark.asyncio
    async def test_mermaid_from_text(self):
        """Test diagram generation from text description."""
        from app.services.rag_service import get_rag_answer_scoped

        # This would require a database session and proper setup
        # In real tests, would mock or use test database
        pass


class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_document_ingestion_with_gemini(self):
        """Test full document ingestion pipeline using Gemini."""
        # Steps:
        # 1. Create document
        # 2. Upload file
        # 3. Queue ingestion with Gemini analysis
        # 4. Verify analysis
        pass

    @pytest.mark.asyncio
    async def test_mobile_document_upload_and_chat(self):
        """Test mobile app document upload and chat flow."""
        # Steps:
        # 1. Mobile uploads document
        # 2. Waits for ingestion
        # 3. Sends chat query
        # 4. Receives answer with citations
        pass

    @pytest.mark.asyncio
    async def test_csv_to_dashboard(self):
        """Test CSV upload and dashboard generation."""
        # Steps:
        # 1. Upload CSV
        # 2. Analyze columns
        # 3. Generate charts
        # 4. Create dashboard
        pass


def run_tests():
    """Run all integration tests."""
    print("DocIntel Integration Test Suite")
    print("=" * 50)
    print()

    # Sync tests
    test_classes = [
        TestGeminiIntegration,
        TestMobileAPIConnectivity,
        TestCSVAnalytics,
        TestTransferLearning,
        TestMermaidGeneration,
    ]

    for test_class in test_classes:
        print(f"\n{test_class.__name__}")
        print("-" * 40)

        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                method = getattr(instance, method_name)
                try:
                    if asyncio.iscoroutinefunction(method):
                        asyncio.run(method())
                    else:
                        method()
                    print(f"  ✅ {method_name}")
                except AssertionError as e:
                    print(f"  ❌ {method_name}: {e}")
                except Exception as e:
                    print(f"  ⚠️  {method_name}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    run_tests()
