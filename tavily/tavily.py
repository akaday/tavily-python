import requests
import json
import warnings
from typing import Literal, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils import get_max_items_from_list
from datatypes import TavilyContextResult, TavilyResponse, TavilyResult

class TavilyClient:
    """
    Tavily API client class.
    """


    def __init__(self, api_key):
        self.base_url = "https://api.tavily.com/search"
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
        }


    def _search(self,
                query: str,
                search_depth: Literal["basic", "advanced"] = "basic",
                topic: Literal["general", "news"] = "general",
                max_results: int = 5,
                include_domains: Sequence[str] = None,
                exclude_domains: Sequence[str] = None,
                include_answer: bool = False,
                include_raw_content: bool = False,
                include_images: bool = False,
                use_cache: bool = True
                ) -> dict:
        """
        Internal search method to send the request to the API.
        """

        data = {
            "query": query,
            "search_depth": search_depth,
            "topic": topic,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
            "max_results": max_results,
            "include_domains": include_domains,
            "exclude_domains": exclude_domains,
            "include_images": include_images,
            "api_key": self.api_key,
            "use_cache": use_cache,
        }
        response = requests.post(self.base_url, data=json.dumps(data), headers=self.headers, timeout=100)

        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()  # Raises a HTTPError if the HTTP request returned an unsuccessful status code


    def search(self,
                query: str,
                search_depth: Literal["basic", "advanced"] = "basic",
                topic: Literal["general", "news"] = "general",
                max_results: int = 5,
                include_domains: Sequence[str] = None,
                exclude_domains: Sequence[str] = None,
                include_answer: bool = False,
                include_raw_content: bool = False,
                include_images: bool = False,
                use_cache: bool = True,
                **kwargs
                ) -> TavilyResponse:
        """
        Combined search method.
        """

        response_dict = self._search(query,
                            search_depth=search_depth,
                            topic=topic,
                            max_results=max_results,
                            include_domains=include_domains,
                            exclude_domains=exclude_domains,
                            include_answer=include_answer,
                            include_raw_content=include_raw_content,
                            include_images=include_images,
                            use_cache=use_cache,
                            **kwargs
                            )
        
        tavily_results = response_dict.get("results", [])
        # TODO CRITICAL Make sure to have good behavior for 'published_date' and 'published date'
       
        if topic == "news":
            for tavily_result in tavily_results:
                if "published date" in tavily_result:
                    tavily_result["published_date"] = tavily_result.pop("published date")

        results = [TavilyResult(**result) for result in tavily_results]
        response_dict["results"] = results

        return TavilyResponse(**response_dict)


    def get_search_context(self,
                           query: str,
                           search_depth: Literal["basic", "advanced"] = "basic",
                           topic: Literal["general", "news"] = "general",
                           max_results: int = 5,
                           include_domains: Sequence[str] = None,
                           exclude_domains: Sequence[str] = None,
                           use_cache: bool = True,
                           max_tokens: int = 4000,
                           **kwargs
                           ) -> str:
        """
        Get the search context for a query. Useful for getting only related content from retrieved websites
        without having to deal with context extraction and limitation yourself.

        max_tokens: The maximum number of tokens to return (based on openai token compute). Defaults to 4000.

        Returns a string of JSON containing the search context up to context limit.
        """

        response_dict = self._search(query,
                            search_depth=search_depth,
                            topic=topic,
                            max_results=max_results,
                            include_domains=include_domains,
                            exclude_domains=exclude_domains,
                            include_answer=False,
                            include_raw_content=False,
                            include_images=False,
                            use_cache=use_cache,
                            **kwargs
                            )
        sources = response_dict.get("results", [])
        context = [TavilyContextResult(url=source["url"], content=source["content"]) for source in sources]
        return json.dumps(get_max_items_from_list(context, max_tokens))


    def qna_search(self, query, search_depth="advanced", **kwargs):
        """
        Q&A search method. Search depth is advanced by default to get the best answer.
        """
        search_result = self._search(query, search_depth=search_depth, include_answer=True, **kwargs)
        return search_result.get("answer", "")


    def get_company_info(self, query, search_depth="advanced", max_results=5, **kwargs):
        """ Q&A search method. Search depth is advanced by default to get the best answer. """

        def _perform_search(topic):
            return self._search(query, search_depth=search_depth, topic=topic,
                                max_results=max_results, include_answer=False, **kwargs)

        with ThreadPoolExecutor() as executor:
            # Initiate the search for each topic in parallel
            future_to_topic = {executor.submit(_perform_search, topic): topic for topic in
                               ["news", "general", "finance"]}

            all_results = []

            # Process the results as they become available
            for future in as_completed(future_to_topic):
                data = future.result()
                if 'results' in data:
                    all_results.extend(data['results'])

        # Sort all the results by score in descending order and take the top 'max_results' items
        sorted_results = sorted(all_results, key=lambda x: x['score'], reverse=True)[:max_results]

        return sorted_results


class Client(TavilyClient):
    """
    Tavily API client class.

    WARNING! This class is deprecated. Please use TavilyClient instead.
    """
    def __init__(self, *args, **kwargs):
        warnings.warn("Client is deprecated, please use TavilyClient instead", DeprecationWarning, stacklevel=2)
        super().__init__(*args, **kwargs)
