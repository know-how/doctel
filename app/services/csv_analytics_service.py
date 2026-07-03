"""
csv_analytics_service.py – CSV parsing, analysis, and chart generation for DocIntel.

Features:
  - CSV parsing with type detection
  - Statistics calculation (mean, median, std dev, etc.)
  - Chart generation (line, bar, scatter, histogram)
  - Dashboard summary generation
"""
import csv
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
import statistics

logger = logging.getLogger(__name__)


class CSVAnalyzer:
    """Analyze CSV files and generate charts/statistics."""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.data: List[Dict[str, Any]] = []
        self.columns: List[str] = []
        self.column_types: Dict[str, str] = {}
        self.numeric_columns: List[str] = []
        self.text_columns: List[str] = []
        self.date_columns: List[str] = []
        
    def load(self, max_rows: int = 100000) -> bool:
        """Load and parse CSV file."""
        if not self.file_path.exists():
            logger.error(f"CSV file not found: {self.file_path}")
            return False
        
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                self.columns = reader.fieldnames or []
                
                for i, row in enumerate(reader):
                    if i >= max_rows:
                        logger.warning(f"CSV truncated at {max_rows} rows")
                        break
                    self.data.append(row)
            
            if not self.data:
                logger.warning(f"CSV file is empty: {self.file_path}")
                return False
            
            # Detect column types
            self._detect_types()
            return True
            
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            return False
    
    def _detect_types(self) -> None:
        """Detect data types for each column."""
        for col in self.columns:
            col_type = self._infer_column_type(col)
            self.column_types[col] = col_type
            
            if col_type == "numeric":
                self.numeric_columns.append(col)
            elif col_type == "date":
                self.date_columns.append(col)
            else:
                self.text_columns.append(col)
    
    def _infer_column_type(self, column: str) -> str:
        """Infer column type from sample values."""
        samples = [str(row.get(column, "")).strip() for row in self.data[:100]]
        samples = [s for s in samples if s]
        
        if not samples:
            return "text"
        
        # Check if numeric
        numeric_count = 0
        for sample in samples:
            try:
                float(sample)
                numeric_count += 1
            except ValueError:
                pass
        
        if numeric_count / len(samples) > 0.8:
            return "numeric"
        
        # Check if date-like
        date_keywords = ["date", "time", "year", "month", "day"]
        if any(kw in column.lower() for kw in date_keywords):
            return "date"
        
        return "text"
    
    def get_summary(self) -> Dict[str, Any]:
        """Generate dashboard summary."""
        summary = {
            "file": str(self.file_path.name),
            "rows": len(self.data),
            "columns": len(self.columns),
            "numeric_columns": self.numeric_columns,
            "text_columns": self.text_columns,
            "date_columns": self.date_columns,
            "column_types": self.column_types,
            "statistics": {},
            "value_distributions": {},
        }
        
        # Calculate statistics for numeric columns
        for col in self.numeric_columns:
            stats = self._calculate_statistics(col)
            if stats:
                summary["statistics"][col] = stats
        
        # Get value distributions for text columns
        for col in self.text_columns[:5]:  # Limit to first 5
            dist = self._get_value_distribution(col)
            if dist:
                summary["value_distributions"][col] = dist
        
        return summary
    
    def _calculate_statistics(self, column: str) -> Optional[Dict[str, float]]:
        """Calculate statistics for numeric column."""
        values = []
        for row in self.data:
            try:
                val = float(row.get(column, 0))
                values.append(val)
            except (ValueError, TypeError):
                pass
        
        if not values:
            return None
        
        return {
            "count": len(values),
            "sum": sum(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "range": max(values) - min(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }
    
    def _get_value_distribution(self, column: str, top_n: int = 10) -> Dict[str, int]:
        """Get top N value occurrences for text column."""
        values = [str(row.get(column, "")).strip() for row in self.data]
        values = [v for v in values if v]
        
        counter = Counter(values)
        return dict(counter.most_common(top_n))
    
    def generate_chart_data(self, chart_type: str, x_column: str, y_column: Optional[str] = None) -> Dict[str, Any]:
        """Generate data for chart visualization."""
        if chart_type == "line":
            return self._generate_line_chart(x_column, y_column)
        elif chart_type == "bar":
            return self._generate_bar_chart(x_column, y_column)
        elif chart_type == "scatter":
            return self._generate_scatter_chart(x_column, y_column)
        elif chart_type == "histogram":
            return self._generate_histogram_chart(x_column)
        elif chart_type == "pie":
            return self._generate_pie_chart(x_column)
        else:
            return {}
    
    def _generate_line_chart(self, x_col: str, y_col: Optional[str]) -> Dict[str, Any]:
        """Generate line chart data."""
        if not y_col:
            y_col = self.numeric_columns[0] if self.numeric_columns else None
        
        if not y_col or x_col not in self.columns or y_col not in self.columns:
            return {}
        
        points = []
        for row in self.data:
            try:
                x = row.get(x_col, "")
                y = float(row.get(y_col, 0))
                if x:
                    points.append({"x": x, "y": y})
            except (ValueError, TypeError):
                pass
        
        return {
            "type": "line",
            "title": f"{y_col} over {x_col}",
            "x_label": x_col,
            "y_label": y_col,
            "data": sorted(points[:500], key=lambda p: p["y"]),
        }
    
    def _generate_bar_chart(self, x_col: str, y_col: Optional[str]) -> Dict[str, Any]:
        """Generate bar chart data."""
        if x_col not in self.columns:
            return {}
        
        # For text column, show value counts
        if x_col in self.text_columns:
            dist = self._get_value_distribution(x_col)
            return {
                "type": "bar",
                "title": f"Distribution of {x_col}",
                "x_label": x_col,
                "y_label": "Count",
                "data": [{"label": k, "value": v} for k, v in dist.items()],
            }
        
        # For numeric column with optional y_col
        if y_col and y_col in self.numeric_columns:
            bars = []
            for row in self.data[:50]:
                try:
                    x = str(row.get(x_col, ""))
                    y = float(row.get(y_col, 0))
                    bars.append({"label": x, "value": y})
                except (ValueError, TypeError):
                    pass
            
            return {
                "type": "bar",
                "title": f"{y_col} by {x_col}",
                "x_label": x_col,
                "y_label": y_col,
                "data": bars,
            }
        
        return {}
    
    def _generate_scatter_chart(self, x_col: str, y_col: Optional[str]) -> Dict[str, Any]:
        """Generate scatter chart data."""
        if not y_col or x_col not in self.numeric_columns or y_col not in self.numeric_columns:
            return {}
        
        points = []
        for row in self.data:
            try:
                x = float(row.get(x_col, 0))
                y = float(row.get(y_col, 0))
                points.append({"x": x, "y": y})
            except (ValueError, TypeError):
                pass
        
        return {
            "type": "scatter",
            "title": f"{y_col} vs {x_col}",
            "x_label": x_col,
            "y_label": y_col,
            "data": points[:500],
        }
    
    def _generate_histogram_chart(self, x_col: str) -> Dict[str, Any]:
        """Generate histogram data."""
        if x_col not in self.numeric_columns:
            return {}
        
        values = []
        for row in self.data:
            try:
                val = float(row.get(x_col, 0))
                values.append(val)
            except (ValueError, TypeError):
                pass
        
        if not values:
            return {}
        
        # Create bins
        min_val, max_val = min(values), max(values)
        num_bins = min(20, max(5, len(values) // 10))
        bin_width = (max_val - min_val) / num_bins if max_val > min_val else 1
        
        bins = [0] * num_bins
        for val in values:
            if bin_width > 0:
                bin_idx = int((val - min_val) / bin_width)
                bin_idx = min(bin_idx, num_bins - 1)
                bins[bin_idx] += 1
        
        bin_labels = [f"{min_val + i * bin_width:.1f}" for i in range(num_bins)]
        
        return {
            "type": "histogram",
            "title": f"Distribution of {x_col}",
            "x_label": x_col,
            "y_label": "Frequency",
            "data": [{"bin": label, "count": count} for label, count in zip(bin_labels, bins)],
        }
    
    def _generate_pie_chart(self, x_col: str) -> Dict[str, Any]:
        """Generate pie chart data."""
        if x_col not in self.text_columns:
            return {}
        
        dist = self._get_value_distribution(x_col, top_n=10)
        
        return {
            "type": "pie",
            "title": f"Breakdown of {x_col}",
            "data": [{"label": k, "value": v} for k, v in dist.items()],
        }
    
    def get_recommendations(self) -> List[Dict[str, str]]:
        """Suggest recommended charts based on data."""
        recommendations = []
        
        # Suggest time series if date column exists
        if self.date_columns and self.numeric_columns:
            recommendations.append({
                "type": "line",
                "title": f"Time Series: {self.numeric_columns[0]}",
                "x_column": self.date_columns[0],
                "y_column": self.numeric_columns[0],
                "reason": "Time series data detected",
            })
        
        # Suggest distribution chart for text column
        if self.text_columns:
            recommendations.append({
                "type": "pie",
                "title": f"Distribution of {self.text_columns[0]}",
                "x_column": self.text_columns[0],
                "reason": "Categorical data available",
            })
        
        # Suggest comparison charts for numeric columns
        if len(self.numeric_columns) >= 2:
            recommendations.append({
                "type": "scatter",
                "title": f"Correlation: {self.numeric_columns[0]} vs {self.numeric_columns[1]}",
                "x_column": self.numeric_columns[0],
                "y_column": self.numeric_columns[1],
                "reason": "Multiple numeric columns",
            })
        
        # Suggest histogram for first numeric column
        if self.numeric_columns:
            recommendations.append({
                "type": "histogram",
                "title": f"Distribution of {self.numeric_columns[0]}",
                "x_column": self.numeric_columns[0],
                "reason": "Numeric data available",
            })
        
        return recommendations


async def analyze_csv_file(file_path: str) -> Dict[str, Any]:
    """Load and analyze a CSV file."""
    analyzer = CSVAnalyzer(file_path)
    if not analyzer.load():
        return {"error": "Failed to load CSV file"}
    
    return {
        "summary": analyzer.get_summary(),
        "recommendations": analyzer.get_recommendations(),
    }


async def generate_csv_chart(file_path: str, chart_type: str, x_column: str, y_column: Optional[str] = None) -> Dict[str, Any]:
    """Generate a specific chart from CSV data."""
    analyzer = CSVAnalyzer(file_path)
    if not analyzer.load():
        return {"error": "Failed to load CSV file"}
    
    chart_data = analyzer.generate_chart_data(chart_type, x_column, y_column)
    if not chart_data:
        return {"error": f"Could not generate {chart_type} chart"}
    
    return chart_data
