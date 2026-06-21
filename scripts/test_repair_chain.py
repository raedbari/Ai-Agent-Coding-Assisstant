from app.llm.repair_chain import request_repair_plan


problem = """
I have this Python error:

Traceback (most recent call last):
  File "<string>", line 1, in <module>
    from app.rag import retrieve_company_context
  File "app/rag.py", line 6, in <module>
    from langchain_huggingface import HuggingFaceEmbeddings
ModuleNotFoundError: No module named 'langchain_huggingface'

Project context:
- Python FastAPI project
- LangChain is used
- Virtual environment is active
- The command was executed from the project root
"""


plan = request_repair_plan(problem)

print(plan.model_dump_json(indent=2))