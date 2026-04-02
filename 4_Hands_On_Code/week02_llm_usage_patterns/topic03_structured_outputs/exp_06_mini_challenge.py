"""
This script corresponds to Day 5-6->Day 2->Hour 1->Mini Challenge->
Build an extract_structured_data() function:
Success Criteria:

Returns valid Pydantic model instance (not dict)
Handles missing optional fields correctly (None, not omitted)
Works on 5 different job posting formats (find real ones, varied formats)
Never returns invalid JSON (use JSON mode or structured outputs)
Boolean fields (remote) correctly inferred even when not explicit ("work from home" → True)
List fields (required_skills) correctly parsed from various formats (comma-separated, bullet points, etc.)
Raises meaningful error if text is completely unrelated to schema
"""
from typing import Type, TypeVar

from openai.types.responses import Response, ParsedResponse
from pydantic import BaseModel, Field

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

from openai import OpenAI, RateLimitError, APIConnectionError, BadRequestError, AuthenticationError, APIError

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key=open_ai_key)

T = TypeVar("T", bound=BaseModel)

SYSTEM_PROMPT_JOB_EXTRACTION = """
You are a job post extractor script. Your job is to extract the details from job description provided to you. It must match the pydantic model provided along.
Example response:
{
"title": "Software Engineer at Adobe",
"company": "Adobe Inc.",
"location": "San Francisco",
"salary_min": 250000,
"salary_max": 350000,
"required_skills": ["Java", "Spring Boot", "MongoDB", "Kafka", "Redis"],
"experience_years": 12,
"remote": true
}
Do not infer or assume values.
If a value is not explicitly mentioned, return null.
Here is the job description to process:
"""

class JobPosting(BaseModel):
    title: str = Field(description="Title of the job post. Examples: Software Engineer at XYZ company or Architect for XYZ Company")
    company: str = Field(description="Name of company. Example: XYZ company.")
    location: str | None = Field(description="Location of the job. Null if not mentioned. Example: Chennai, Dubai, Mumbai, San Francisco")
    salary_min: int | None = Field(description="Minimum Salary for the job. Example: Salary $120K-$150K, then salary_min is $120K. "
                                               "Else if salary is $120K, then becomes null because this is the max salary "
                                               "and will be set to salary_max.")
    salary_max: int | None = Field(description="Minimum Salary for the job. Example: Salary $120K-$150K, then salary_max is $150K. "
                                               "Else if salary is $120K, then salary_max becomes $120K")
    required_skills: list[str] = Field(description="Skills to have for applying to this job. "
                                                   "Example: [Spring boot, Java, Python, AI/ML] or [Java, Javascript, Kafka, Redis]")
    experience_years: int | None = Field(description="Experience in years required to apply for the job. Example: 10, 15, 5. null if not mentioned")
    remote: bool = Field(description="If the job is a remote job or office presence is required. If not present in job descriptions assume false")

def generate_openai_gpt_parsed_response(prompt: str, schema: Type[T], model: str = "gpt-5.4-mini") -> ParsedResponse[T] | None:
    """
    Takes a prompt and model. Returns the response
    :param schema:
    :param prompt: The prompt that user sends
    :param model: The gpt model that will process the prompt. Defaults to gpt-5.4-mini
    :return: openai.resources.responses.Response
    """

    try:
        response = openai_client.responses.parse(
            model=model,
            input=prompt,
            max_output_tokens=300,
            temperature=0.5,
            text_format=schema
        )

        if response is not None:
            logger.info("Response created successfully")
            dump_json(response.model_dump(), "GPT Response For Run")
            return response

    except APIConnectionError as e:
        logger.exception("Network/API connection issue")
    except BadRequestError as e:
        logger.exception("Bad request: prompt/model/params issue")
    except APIError as e:
        logger.exception("OpenAI server/API error")
    except Exception as e:
        logger.exception("Unexpected failure")

    return None


def extract_structured_data(text:str, schema: Type[T], model:str="gpt-5.4-mini") -> None:
    """
    Adds system prompt. Prints output of LLM for job description
    :param text:
    :param schema:
    :param model:
    :return: None
    """
    prompt = ""
    if schema is JobPosting:
        prompt = SYSTEM_PROMPT_JOB_EXTRACTION + text
    else:
        # Must add other pydantic models and update elif
        raise ValueError("Unknown schema")

    response = generate_openai_gpt_parsed_response(prompt=prompt, schema=schema)
    logger.info(f"JSON Response: {response.output_parsed.model_dump()}")
    dump_json(response.output_parsed.model_dump(), "JobPosting Object")

if __name__ == "__main__":
    # Sample1 — Structured with salary range:
    prompt1 = """Senior Backend Engineer at Stripe

    Location: San Francisco, CA (Hybrid)
    Salary: $180,000 - $250,000 annually
    
    We're looking for a Senior Backend Engineer to join our Payments team. You'll design and build the infrastructure that moves money across the globe.
    
    Requirements:
    - 5+ years of experience in backend development
    - Strong proficiency in Ruby, Go, or Java
    - Experience with distributed systems
    - Familiarity with PostgreSQL and Redis
    - Understanding of financial systems is a plus"""

    # Sample2 — Casual prose, no explicit salary:
    prompt2 = """DevOps Engineer - Acme Corp
    
    Hey! We're a fast-growing startup looking for a DevOps wizard to join our team. You'll be working completely remotely from anywhere in the world.
    
    We need someone who knows their way around Kubernetes, Docker, and AWS. Terraform experience is a big plus. CI/CD pipelines should be second nature to you. We're looking for at least 3 years of experience.
    
    Competitive salary and equity. Let's chat!"""

    # Sample3 — Bullet - heavy, explicit remote:
    prompt3 = """
    JOB TITLE: Full Stack Developer
    COMPANY: TechFlow Solutions
    LOCATION: Work from home (US timezone preferred)
    COMPENSATION: $120k-$160k base + bonus
    
    MUST HAVE:
    - React.js, Node.js
    - TypeScript
    - REST APIs and GraphQL
    - SQL databases
    - 4 years minimum experience
    
    NICE TO HAVE:
    - AWS or GCP
    - Docker"""

    # Sample 4 — Minimal info, on-site:
    prompt4 = """
    Junior Data Analyst
    
    DataCrunch Inc. is hiring a Junior Data Analyst for our NYC office. This is an in-office position.
    
    Skills: Python, SQL, Excel, Tableau
    Entry level welcome, but some internship experience preferred."""

    # Sample 5 — European format, different currency:
    prompt5 = """
    Machine Learning Engineer
    Berlin, Germany | Hybrid (3 days office)
    
    Zalando SE
    
    Salary range: €75.000 - €95.000 per year
    
    About the role:
    Join our ML platform team to build recommendation systems at scale. 
    
    Required qualifications:
    Python, PyTorch or TensorFlow, MLOps experience, familiarity with Kubernetes and Spark. 
    We expect candidates to have 2-4 years of relevant experience in machine learning engineering or related fields."""


    # extract_structured_data(prompt1, JobPosting)

    # extract_structured_data(prompt2, JobPosting)

    # extract_structured_data(prompt3, JobPosting)

    # extract_structured_data(prompt4, JobPosting)

    extract_structured_data(prompt5, JobPosting)