"""
This script corresponds to Day 5-6->Day 6->Hour 1->Mini Challenge->

Build a prompt (not code, just the prompt) for this task:

Task: Extract structured information from job posting text.

Input: Raw job posting text (varies wildly in format) Output: JSON with fields: title, company, location, salary_range (null if not mentioned), required_skills (array), experience_years (null if not mentioned)

Success Criteria:

Test your prompt on 5 different job postings (find real ones online)
All 5 return valid JSON that parses without errors
Fields are correctly extracted (manually verify each)
Handles missing information gracefully (null, not made up)
Works without modification across different job posting formats
Deliverable:

Your final prompt (system + user template)
Notes on iterations: what you tried that didn't work, what fixed it

NOTES: This asks for just prompt, but I wrote a script because I wanted to capture the outputs during each iteration.
"""
from typing import Literal
from openai.types.responses import Response

import sys

from common.logger import get_logger
from common.config import get_config
from common.dumper import dump_json

from openai import OpenAI

logger = get_logger(__file__)
config = get_config()
open_ai_key = config.get("OPEN_AI_KEY")
openai_client = OpenAI(api_key = open_ai_key)

job_extractor_prompt = """
You are a job post extractor script. Your job is to extract the following details from the job description provided to you.
1. title: Title of the job post | Type: String | Examples: Software Engineer at XYZ company or Architect for XYZ Company
2. company: Name of company | Type: String | Example: XYZ company.
3. salary_range: Salary if mentioned. Null if not mentioned | Type: float | Example: 120000 or 250000
4. currency_code: Currency code of mentioned salary above. Null if salary is null | Type: string | Example: USD, INR, SGD
5. salary_period: Period for which the above salary is paid for. Null if salary is null | Type: string | Example: Monthly, Yearly, Quarterly.
6. location: Location of the job. Null if not mentioned | Type: string | Example: Chennai, Dubai, Mumbai, San Francisco
7. required_skills: Skills to have for applying to this job | Type: Array | [Spring boot, Java, Python, AI/ML] or [Java, Javascript, Kafka, Redis]
8. experience_years: Experience in years required to apply for the job. null if not mentioned | Type: integer | Example: 10, 15, 5
Return ONLY valid JSON. 
Do not include markdown, explanations, or code blocks. 
The response must be directly parseable using json.loads().
Example response:
{
"title": "Software Engineer at Adobe",
"company": "Adobe Inc.",
"salary_range": "250000",
"currency_code": "USD",
"salary_period": "Yearly",
"location": "San Francisco",
"required_skills": ["Java", "Spring Boot", "MongoDB", "Kafka", "Redis"],
"experience_years": "12",
}
Do not infer or assume values.
If a value is not explicitly mentioned, return null.
Here is the job description to process:
"""

def generate_openai_gpt_response(prompt: str, model: str = "gpt-5.4-mini") -> Response | None:
    """
    Takes a prompt and model. Returns the response
    :param prompt: The prompt that user sends
    :param model: The gpt model that will process the prompt. Defaults to gpt-5.4-mini
    :return: openai.resources.responses.Response
    """

    try:
        response = openai_client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=500,
            temperature=0
        )

        if response is not None:
            logger.info("Response created successfully")
            return response
    except Exception as e:
        logger.error("Error %s", e)
        return None

def job_extractor_orchestrator() -> None:
    """
    processes job descriptions and prints json.
    :return:
    """
    job_descriptions = [
        # 1. Perfect match description
        """We are hiring a Senior Software Engineer at XYZ Company.
    Location: Chennai, India
    Salary: INR 25,00,000 per year
    Experience Required: 5 years
    Skills Required: Java, Spring Boot, Kafka, Redis, Microservices
    Join our backend team to build scalable distributed systems and APIs for millions of users.""",

        # 2. Some misses (missing salary + unclear experience)
        """Looking for a Backend Developer for ABC Technologies.
    Based in Mumbai.
    Must have strong experience in Python, Django, and PostgreSQL.
    Experience: Mid-level candidates preferred.
    Salary: Competitive, as per industry standards.
    You will work on building APIs and improving system performance.""",

        # 3. Differently worded / ambiguous
        """An exciting opportunity with a fast-growing fintech startup.
    Role: Platform Architect
    Compensation: Around 20–30 LPA depending on fit
    Location flexibility: Remote (India preferred)
    What we’re looking for:
    - Deep experience with event-driven systems
    - Strong knowledge of Java, Kafka, and cloud-native architecture
    - Typically 8+ years in backend or platform engineering
    You’ll design systems that handle high-throughput financial transactions."""
    ]

    count = 1
    for job in job_descriptions:
        final_prompt = job_extractor_prompt + job
        logger.info(f"Final prompt: {final_prompt}")
        answer_object = generate_openai_gpt_response(job_extractor_prompt + job)

        if answer_object is not None:
            dump_json(answer_object.model_dump(), f"Job Description {count}")
            logger.info("Answer for job description %d: \n%s", count, answer_object.output_text)
        else:
            logger.error("No response returned")

        count += 1
        logger.info("-" * 150)

if __name__ == "__main__":
    job_extractor_orchestrator()