import json
import urllib.request
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

mcp = FastMCP(host="0.0.0.0", stateless_http=True)


class ClinicalTrialsAPI:
    """Wrapper around ClinicalTrials.gov API

    This wrapper will use ClinicalTrials.gov API to search for clinical trials and fetch them.
    """

    def __init__(self):
        # Search all trial statuses (RECRUITING, COMPLETED, etc.) for broader results
        self.base_url = "https://clinicaltrials.gov/api/v2/studies?format=json&query.term="
        self.top_k_results = 20

    def run(self, query: str) -> Dict:
        """
        The run function takes in a query string and returns the top k results from clinicaltrials.gov
            Args:
                query (str): The search term to be queried on clinicaltrials.gov

        :param self: Represent the instance of the class
        :param query: Pass the query string to the api
        :return: A dictionary
        """
        # Add pageSize parameter to limit results
        url = self.base_url + query + f"&pageSize={self.top_k_results}"
        url = url.replace(" ", "+")
        print(f"Querying ClinicalTrials.gov: {url}")
        
        try:
            # Add headers to mimic browser request
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; ClinicalTrialsBot/1.0)',
                    'Accept': 'application/json'
                }
            )
            result = urllib.request.urlopen(req, timeout=30)
            decoded_result = result.read().decode("utf-8")
            output = json.loads(decoded_result)
            
            if output is not None:
                if "studies" in output:
                    if len(output["studies"]) > 0:
                        studies = self._parse_trial(output)
                        if len(studies) > 0:
                            return {"studies": studies, "total_count": len(studies)}
                        else:
                            return {"output": "Could not parse any studies from the results"}
                    else:
                        return {"output": f"No clinical trials found for query: {query}"}
                else:
                    return {"output": "Invalid response format from ClinicalTrials.gov API"}
            else:
                return {"output": "Empty response from ClinicalTrials.gov API"}

        except urllib.error.HTTPError as e:
            error_msg = f"HTTP Error {e.code}: {e.reason}"
            print(f"Request failed: {error_msg}")
            print(f"URL: {url}")
            return {"error": error_msg, "url": url, "suggestion": "Try a simpler search term or check if the API is available"}
        except urllib.error.URLError as e:
            error_msg = f"URL Error: {e.reason}"
            print(f"Request failed: {error_msg}")
            return {"error": error_msg, "suggestion": "Check network connectivity or API availability"}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"Request failed: {error_msg}")
            return {"error": error_msg}

    def _parse_trial(self, trials: Dict) -> list:
        """
        The _parse_trial function takes in a dictionary of trials and returns a list of dictionaries.
        Each dictionary contains the following keys:
            - Organization (str)
            - OfficialTitle (str)
            - StartDate (str)
            - CompletionDate (str)  # This is an optional key, so it may not be present in every trial.

        :param self: Represent the instance of the class
        :param trials: Pass in the dictionary that is returned from the _get_trials function
        :return: A list of dictionaries
        """
        studies = []

        for trial in trials["studies"]:
            try:
                study = {}
                protocol = trial.get("protocolSection", {})
                
                # Identification
                identification = protocol.get("identificationModule", {})
                study["NCTId"] = identification.get("nctId", "N/A")
                study["Organization"] = identification.get("organization", {}).get("fullName", "N/A")
                study["OfficialTitle"] = identification.get("officialTitle", "N/A")
                
                # Status
                status = protocol.get("statusModule", {})
                study["OverallStatus"] = status.get("overallStatus", "N/A")
                study["StartDate"] = status.get("startDateStruct", {}).get("date", "N/A")
                study["CompletionDate"] = status.get("completionDateStruct", {}).get("date", "N/A")
                
                # Description
                description = protocol.get("descriptionModule", {})
                study["Description"] = description.get("briefSummary", "N/A")
                
                # Outcomes
                if "outcomesModule" in protocol:
                    outcomes = protocol["outcomesModule"].get("primaryOutcomes", [])
                    study["PrimaryOutcomes"] = outcomes if outcomes else "N/A"
                else:
                    study["PrimaryOutcomes"] = "N/A"
                
                # Eligibility
                eligibility = protocol.get("eligibilityModule", {})
                study["EligibilityCriteria"] = eligibility.get("eligibilityCriteria", "N/A")
                
                # Adverse events (if available)
                if "adverseEventsModule" in protocol:
                    study["AdverseEvents"] = "Available in full trial data"
                
                studies.append(study)
            except Exception as e:
                print(f"Error parsing trial: {e}")
                continue

        return studies

@mcp.tool()
def run_clinical_trial(query: str):
    clinical_trials = ClinicalTrialsAPI()
    studies = clinical_trials.run(query)
    return studies
    
if __name__=="__main__":
    mcp.run(transport="streamable-http")