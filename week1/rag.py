#!/usr/bin/env python
# coding: utf-8

# In[1]:

from openai import OpenAI

openai_client = OpenAI()


# In[2]:


def llm(user_prompt, instructions=None, model="gpt-4o-mini"):
    messages = []

    if instructions:
        messages.append({
            "role": "system",
            "content": instructions
        })

    messages.append({
        "role": "user",
        "content": user_prompt
    })

    response = openai_client.responses.create(
        model=model,
        input=messages
    )

    return response.output_text


# In[3]:


llm('When does the course start?')


# In[5]:


import requests 

docs_url = 'https://github.com/alexeygrigorev/llm-rag-workshop/raw/main/notebooks/documents.json'
docs_response = requests.get(docs_url)
documents_raw = docs_response.json()

documents = []

for course in documents_raw:
    course_name = course['course']

    for doc in course['documents']:
        doc['course'] = course_name
        documents.append(doc)


# In[12]:


documents[11]


# In[13]:


len(documents)


# In[14]:


from minsearch import Index


# In[15]:


index = Index(
    text_fields=["question", "text", "section"],
    keyword_fields=["course"]
)

index.fit(documents)


# In[20]:


def search(question):
    return index.search(
        question,
        boost_dict={'question': 3.0, 'section': 0.3},
        filter_dict={'course': 'data-engineering-zoomcamp'},
        num_results=5
    )


# In[21]:


question = 'I just discovered the course, can I join now?'


# In[23]:


search_results = search(question)


# In[26]:


instructions = """
You're a course teaching assistant. Answer the QUESTION based on the CONTEXT from the FAQ database.
Use only the facts from the CONTEXT when answering the QUESTION.
""".strip()

prompt_template = """
<QUESTION>
{question}
</QUESTION>

<CONTEXT>
{context}
</CONTEXT>
""".strip()


# In[28]:


import json


# In[31]:


def build_prompt(question, search_results):
    search_json = json.dumps(search_results)
    return prompt_template.format(
        question=question,
        context=search_json
    )


# In[33]:


def rag(question):
    search_results = search(question)
    user_prompt = build_prompt(question, search_results)
    return llm(user_prompt, instructions=instructions)


# In[34]:


rag(question)


# In[ ]:




