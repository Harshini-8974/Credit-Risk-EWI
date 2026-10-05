from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

playbook_path = "playbook.txt"

loader = TextLoader(playbook_path, encoding="utf-8")
documents = loader.load()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=100
)

chunks = text_splitter.split_documents(documents)

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vector_db = FAISS.from_documents(
    chunks,
    embeddings
)

retriever = vector_db.as_retriever(
    search_kwargs={"k": 6}
)
#testing block
if __name__ == "__main__":
    query = """
    What recommended actions apply when
    Inbound Cash Flow Decline (KPI-004) and
    Sustained High Utilization (KPI-002) occur together?
    """
    results = retriever.invoke(query)
    print("\nRetrieved documents:\n")
    for i, result in enumerate(results):
        print(f"\n--- RESULT {i + 1} ---")
        print(result.page_content)
        print("--------------------")