import os
import time
import json
import hashlib
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Union, Any, List
from pydantic import BaseModel

from structuredOutput.summary import SummaryService, SummaryModel
from structuredOutput.recommendations import RecommendationService, RecommendationModel
from structuredOutput.visuals import VisualsService, ChartSpec

class ServiceResult(BaseModel):
    """Container for service execution results with metadata."""
    success: bool = True
    data: Any = None
    execution_time: float = 0
    error_message: Optional[str] = None

class FastIntelligenceOrchestrator:
    """Optimized orchestrator with fast local processing where possible."""
    
    def __init__(self):
        self.summary_service = SummaryService()
        self.recommendation_service = RecommendationService()
        self.visuals_service = VisualsService()
        
        # Create cache directory if it doesn't exist
        self.cache_dir = os.path.join(os.path.dirname(__file__), '..', '.cache')
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _get_cache_path(self, file_id: str) -> str:
        """Get the cache path for a file ID."""
        return os.path.join(self.cache_dir, f"{file_id}.json")
    
    def _get_file_id(self, file_url: Optional[str] = None, content: Optional[Union[str, bytes]] = None) -> str:
        """Generate a unique ID for the file content or URL."""
        if file_url:
            return hashlib.md5(file_url.encode()).hexdigest()
        elif content:
            if isinstance(content, str):
                return hashlib.md5(content.encode()).hexdigest()
            else:
                return hashlib.md5(content).hexdigest()
        return "unknown"
    
    def _get_cached_result(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get cached result for the file ID."""
        cache_path = self._get_cache_path(file_id)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cached_data = json.load(f)
                    # Convert cached data to ServiceResult objects
                    results = {}
                    for service_name, result_data in cached_data.items():
                        results[service_name] = ServiceResult(**result_data)
                    return results
            except:
                return None
        return None
    
    def _save_to_cache(self, file_id: str, results: Dict[str, ServiceResult]) -> None:
        """Save results to cache."""
        cache_path = self._get_cache_path(file_id)
        try:
            # Convert ServiceResult objects to dictionaries
            cache_data = {k: v.dict() for k, v in results.items()}
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)
        except:
            pass
    
    def _download_file(self, url: str) -> bytes:
        """Download a file from a URL with a short timeout to improve latency."""
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    
    def _detect_mime_type(self, content: Union[str, bytes], mime_type: Optional[str] = None) -> str:
        """Detect MIME type from content if not provided."""
        if mime_type:
            return mime_type
            
        if isinstance(content, bytes):
            # Try to detect CSV
            try:
                sample = content[:1000].decode('utf-8')
                lines = sample.splitlines()
                if len(lines) > 1 and ',' in lines[0]:
                    return 'text/csv'
            except:
                pass
                
            # Try other simple detections
            if content.startswith(b'%PDF'):
                return 'application/pdf'
            elif content.startswith(b'PK'):
                return 'application/zip'  # Could be XLSX, DOCX, etc.
            
        elif isinstance(content, str):
            lines = content.splitlines()[:5]
            if len(lines) > 1 and ',' in lines[0]:
                return 'text/csv'
                
        return 'text/plain'
    
    def _is_csv_content(self, content: Union[str, bytes]) -> bool:
        """Check if content is likely CSV format."""
        if isinstance(content, bytes):
            try:
                text_sample = content[:1000].decode('utf-8')
            except:
                return False
        else:
            text_sample = content[:1000]
            
        lines = text_sample.splitlines()
        if len(lines) > 1:
            return lines[0].count(',') >= 2
        return False
    
    def analyze(self, file_url: Optional[str] = None, content: Optional[Union[str, bytes]] = None, 
                mime_type: Optional[str] = None, use_cache: bool = True) -> Dict[str, ServiceResult]:
        """
        Analyze content from file_url or provided content.
        Returns a dictionary with results from each service.
        
        Args:
            file_url: URL to download the file from
            content: Content to analyze directly
            mime_type: Optional MIME type of the content
            use_cache: Whether to use cached results if available
        """
        start_time = time.time()
        
        try:
            # Get file content
            if file_url:
                try:
                    file_id = self._get_file_id(file_url=file_url)
                    
                    # Try cache first if enabled
                    if use_cache:
                        cached_results = self._get_cached_result(file_id)
                        if cached_results:
                            print(f"✅ Using cached results for {file_url}")
                            return cached_results
                    
                    content = self._download_file(file_url)
                except Exception as e:
                    error_msg = f"Failed to download file: {str(e)}"
                    return {
                        "error": ServiceResult(success=False, error_message=error_msg)
                    }
            elif content is None:
                return {
                    "error": ServiceResult(success=False, error_message="Either file_url or content must be provided")
                }
                
            file_id = self._get_file_id(file_url=file_url, content=content)
            
            # Try cache first if enabled and we didn't already check above
            if use_cache and not file_url:
                cached_results = self._get_cached_result(file_id)
                if cached_results:
                    print(f"✅ Using cached results")
                    return cached_results
            
            # Detect MIME type if not provided
            detected_mime_type = self._detect_mime_type(content, mime_type)
            
            # For small CSV files, use fast local processing
            if detected_mime_type == 'text/csv' and self._is_csv_content(content):
                print("📊 Using optimized CSV processing pipeline")
                results = self._process_csv_fast(content)
                
                # Cache results
                if use_cache:
                    self._save_to_cache(file_id, results)
                    
                return results
            
            # Regular processing with parallel execution
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(self._run_summary_service, content, detected_mime_type): "summary",
                    executor.submit(self._run_recommendation_service, content, detected_mime_type): "recommendations", 
                    executor.submit(self._run_visuals_service, content, detected_mime_type): "visuals"
                }
                
                results = {}
                for future in as_completed(futures):
                    service_name = futures[future]
                    try:
                        results[service_name] = future.result()
                    except Exception as e:
                        results[service_name] = ServiceResult(
                            success=False,
                            error_message=f"Service execution error: {str(e)}",
                            execution_time=time.time() - start_time
                        )
            
            # Cache results
            if use_cache:
                self._save_to_cache(file_id, results)
                
            return results
            
        except Exception as e:
            return {
                "error": ServiceResult(
                    success=False,
                    error_message=f"Orchestration error: {str(e)}",
                    execution_time=time.time() - start_time
                )
            }
    
    def _process_csv_fast(self, content: Union[str, bytes]) -> Dict[str, ServiceResult]:
        """Fast path for CSV processing using local analysis where possible."""
        from tools.fast_llm_client import analyze_csv_locally
        
        start_time = time.time()
        results = {}
        
        try:
            # Convert bytes to string if needed
            if isinstance(content, bytes):
                try:
                    content_str = content.decode('utf-8')
                except UnicodeDecodeError:
                    content_str = content.decode('latin-1', errors='replace')
            else:
                content_str = content
                
            # Analyze CSV locally first to extract structure and statistics
            local_analysis = analyze_csv_locally(content_str)
            
            # Run the services with local analysis to speed up processing
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(self._run_summary_service_fast, content_str, local_analysis): "summary",
                    executor.submit(self._run_recommendation_service_fast, content_str, local_analysis): "recommendations", 
                    executor.submit(self._run_visuals_service_fast, content_str, local_analysis): "visuals"
                }
                
                for future in as_completed(futures):
                    service_name = futures[future]
                    try:
                        results[service_name] = future.result()
                    except Exception as e:
                        results[service_name] = ServiceResult(
                            success=False,
                            error_message=f"Service execution error: {str(e)}",
                            execution_time=time.time() - start_time
                        )
            
            return results
            
        except Exception as e:
            error_result = ServiceResult(
                success=False,
                error_message=f"CSV fast processing error: {str(e)}",
                execution_time=time.time() - start_time
            )
            return {"error": error_result}
    
    def _run_summary_service(self, content: Union[str, bytes], mime_type: Optional[str]) -> ServiceResult:
        """Run the summary service."""
        start_time = time.time()
        try:
            result = self.summary_service.generate_summary(content, mime_type=mime_type)
            return ServiceResult(
                success=True,
                data=result,
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ServiceResult(
                success=False,
                error_message=f"Summary service error: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def _run_recommendation_service(self, content: Union[str, bytes], mime_type: Optional[str]) -> ServiceResult:
        """Run the recommendation service."""
        start_time = time.time()
        try:
            result = self.recommendation_service.generate_recommendations(content, mime_type=mime_type)
            return ServiceResult(
                success=True,
                data=result,
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ServiceResult(
                success=False,
                error_message=f"Recommendation service error: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def _run_visuals_service(self, content: Union[str, bytes], mime_type: Optional[str]) -> ServiceResult:
        """Run the visuals service."""
        start_time = time.time()
        try:
            result = self.visuals_service.recommend_charts(content, mime_type=mime_type)
            return ServiceResult(
                success=True,
                data=result,
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ServiceResult(
                success=False,
                error_message=f"Visuals service error: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def _run_summary_service_fast(self, content: str, local_analysis: Dict[str, Any]) -> ServiceResult:
        """Run summary service with local analysis for faster processing."""
        start_time = time.time()
        try:
            # If we have enough data locally, we can generate a simple summary without LLM
            if not local_analysis.get('error'):
                from structuredOutput.summary import SummaryModel
                
                # Get column names and sample data
                headers = local_analysis.get('headers', [])
                row_count = local_analysis.get('row_count', 0)
                
                # Create a simple summary based on local analysis
                summary = {
                    "title": f"CSV Data Analysis ({row_count} rows)",
                    "summary": f"Dataset with {row_count} rows and {len(headers)} columns. Columns include: {', '.join(headers)}",
                    "key_points": [
                        f"The dataset contains {row_count} records",
                        f"{len(local_analysis.get('numeric_columns', {}))} numeric columns and {len(local_analysis.get('categorical_columns', {}))} categorical columns"
                    ],
                    "recommended_charts": []
                }
                
                # Add insights about numeric columns
                for col_name, stats in local_analysis.get('numeric_columns', {}).items():
                    summary["key_points"].append(
                        f"{col_name}: Range {stats['min']:.2f} to {stats['max']:.2f}, Mean {stats['mean']:.2f}"
                    )
                
                # Add insights about categorical columns
                for col_name, data in local_analysis.get('categorical_columns', {}).items():
                    if data.get('most_common'):
                        top_value = data['most_common'][0][0]
                        summary["key_points"].append(
                            f"{col_name}: {data['unique_values']} unique values, most common: {top_value}"
                        )
                
                # Return fast local results
                return ServiceResult(
                    success=True,
                    data=SummaryModel(**summary),
                    execution_time=time.time() - start_time
                )
            
            # Fall back to normal processing if local analysis failed
            result = self.summary_service.generate_summary(content, mime_type='text/csv')
            return ServiceResult(
                success=True,
                data=result,
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ServiceResult(
                success=False,
                error_message=f"Fast summary service error: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def _run_recommendation_service_fast(self, content: str, local_analysis: Dict[str, Any]) -> ServiceResult:
        """Run recommendation service with local analysis for faster processing."""
        start_time = time.time()
        try:
            # Generate recommendations based on local analysis without LLM if possible
            if not local_analysis.get('error'):
                from structuredOutput.recommendations import RecommendationModel
                
                recommendations = []
                
                # Look for common procurement columns
                headers = local_analysis.get('headers', [])
                has_amount = any(h.lower() in ('amount', 'cost', 'spend', 'price') for h in headers)
                has_supplier = any(h.lower() in ('supplier', 'vendor', 'company') for h in headers)
                has_category = any(h.lower() in ('category', 'type', 'group', 'product') for h in headers)
                
                # Generate basic procurement recommendations
                if has_amount and has_supplier:
                    recommendations.append("Consider consolidating suppliers to reduce procurement complexity and increase buying power")
                    recommendations.append("Implement a spend analysis program to track and optimize procurement costs")
                    
                if has_category:
                    recommendations.append("Develop category-specific sourcing strategies to optimize spend")
                    
                # Add general recommendations
                recommendations.extend([
                    "Establish formal supplier relationship management processes to improve collaboration and performance",
                    "Consider implementing an e-procurement system to streamline purchasing processes",
                    "Regularly review procurement data to identify cost-saving opportunities and compliance issues"
                ])
                
                return ServiceResult(
                    success=True,
                    data=RecommendationModel(recommendations=recommendations),
                    execution_time=time.time() - start_time
                )
            
            # Fall back to normal processing if local analysis failed
            result = self.recommendation_service.generate_recommendations(content, mime_type='text/csv')
            return ServiceResult(
                success=True,
                data=result,
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ServiceResult(
                success=False,
                error_message=f"Fast recommendation service error: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def _run_visuals_service_fast(self, content: str, local_analysis: Dict[str, Any]) -> ServiceResult:
        """Run visuals service with local analysis for faster processing."""
        start_time = time.time()
        try:
            # Generate chart suggestions based on local analysis without LLM if possible
            if not local_analysis.get('error'):
                from structuredOutput.visuals import ChartSpec
                
                charts = []
                headers = local_analysis.get('headers', [])
                
                # Look for date/time columns for time series
                date_col = None
                for header in headers:
                    if any(term in header.lower() for term in ['date', 'time', 'year', 'month', 'day']):
                        date_col = header
                        break
                
                # Extract numeric and categorical columns
                numeric_cols = list(local_analysis.get('numeric_columns', {}).keys())
                categorical_cols = list(local_analysis.get('categorical_columns', {}).keys())
                
                # Bar chart for categorical + numeric columns
                if categorical_cols and numeric_cols:
                    cat_col = categorical_cols[0]
                    num_col = numeric_cols[0]
                    
                    bar_chart = ChartSpec(
                        chart_type="bar",
                        purpose=f"Bar chart showing {num_col} by {cat_col}",
                        x_axis=cat_col,
                        y_axis=num_col,
                        data={"labels": cat_col, "values": num_col}
                    )
                    charts.append(bar_chart)
                
                # Pie chart for categorical data
                if categorical_cols:
                    cat_col = categorical_cols[0]
                    pie_chart = ChartSpec(
                        chart_type="pie",
                        purpose=f"Pie chart showing distribution of {cat_col}",
                        notes=f"Visual representation of {cat_col} distribution"
                    )
                    charts.append(pie_chart)
                
                # Line chart for time series data
                if date_col and numeric_cols:
                    num_col = numeric_cols[0]
                    line_chart = ChartSpec(
                        chart_type="line",
                        purpose=f"Line chart showing {num_col} over time",
                        x_axis=date_col,
                        y_axis=num_col,
                        notes=f"Trend analysis of {num_col} by {date_col}"
                    )
                    charts.append(line_chart)
                
                # Create at least one default chart if none were created
                if not charts:
                    charts.append(ChartSpec(
                        chart_type="text_summary",
                        purpose="This dataset contains primarily textual or non-standard data that requires custom visualization"
                    ))
                
                return ServiceResult(
                    success=True,
                    data=charts,
                    execution_time=time.time() - start_time
                )
            
            # Fall back to normal processing if local analysis failed
            result = self.visuals_service.recommend_charts(content, mime_type='text/csv')
            return ServiceResult(
                success=True,
                data=result,
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ServiceResult(
                success=False,
                error_message=f"Fast visuals service error: {str(e)}",
                execution_time=time.time() - start_time
            )
