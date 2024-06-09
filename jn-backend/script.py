#!/usr/bin/env python
# coding: utf-8

import sys
import json
from tqdm import tqdm
import pandas as pd
from openai import OpenAI
import os
import websockets
import asyncio

async def send_progress(message):
    uri = "ws://localhost:3000"
    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps({"type": "progress", "message": message}))

def main():
    input_data = sys.stdin.read()
    params = json.loads(input_data)

    api_key = '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'  # Manually input your API key here 
    client = OpenAI(api_key=api_key)

    assistant = client.beta.assistants.create(
        name="Data Analyst",
        instructions="You are an expert Data Analyst. Use your knowledge base to answer questions about the reports. Keep your answers as brief as possible. In your answers, specify only the data for FY 2022-23, and only mention the answer along with the unit mentioned in each query. Avoid extraneous output. Do not make assumptions and be as accurate as possible.",
        model="gpt-3.5-turbo",
        tools=[{"type": "file_search"}],
    )

    vector_store_name = params["vector_store_name"]
    vector_store = client.beta.vector_stores.create(name=str(vector_store_name))
    pdf_file_path = params["pdf_file_path"]

    file_paths = [str(pdf_file_path)]
    file_streams = [open(file_path, "rb") for file_path in file_paths]

    try:
        file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id, files=file_streams
        )
    finally:
        for stream in file_streams:
            stream.close()

    assistant = client.beta.assistants.update(
        assistant_id=assistant.id,
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}}
    )

    excel_file_path = 'questions.xlsx'  # Assuming this file is in the same directory
    df = pd.read_excel(excel_file_path, engine='openpyxl')  # Specify the engine

    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    def get_answer(question, section):
        thread = client.beta.threads.create(
            messages=[
                {"role": "user", "content": question}
            ]
        )
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id, assistant_id=assistant.id
        )
        messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))

        if not messages:
            return "No response received."

        message_content = messages[0].content[0].text
        annotations = message_content.annotations
        citations = []
        for index, annotation in enumerate(annotations):
            message_content.value = message_content.value.replace(annotation.text, f"[{index}]")
            if file_citation := getattr(annotation, "file_citation", None):
                cited_file = client.files.retrieve(file_citation.file_id)
                citations.append(f"[{index}] {cited_file.filename}")
        answer = message_content.value + "\n" + "\n".join(citations)
        return answer

    async def process_data():
        tqdm.pandas()
        total_rows = len(df)
        progress_bar = tqdm(total=total_rows)
        for idx, row in df.iterrows():
            df.at[idx, 'Answer'] = get_answer(row['Data Points'], row['Section/ Point'])
            progress_bar.update(1)
            await send_progress(f"Processed {idx + 1}/{total_rows}")
        progress_bar.close()

        for f in os.listdir(output_dir):
            os.remove(os.path.join(output_dir, f))

        grouped = df.groupby('Area of Analysis')
        for category, group_df in grouped:
            file_name = os.path.join(output_dir, f"{category}.xlsx")
            group_df.to_excel(file_name, index=False)

        output_file = os.path.join(output_dir, "Ragresults.xlsx")
        df.to_excel(output_file, index=False)

        await send_progress("Processing complete")

    asyncio.run(process_data())

if __name__ == "__main__":
    main()


# #!/usr/bin/env python
# # coding: utf-8

# import sys
# import json
# from tqdm import tqdm
# import pandas as pd
# from openai import OpenAI
# import os

# def main():
#     input_data = sys.stdin.read()
#     params = json.loads(input_data)

#     api_key = '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'  # Manually input your API key here
#     client = OpenAI(api_key=api_key)

#     assistant = client.beta.assistants.create(
#         name="Data Analyst",
#         instructions="You are an expert Data Analyst. Use your knowledge base to answer questions about the reports. Keep your answers as brief as possible. In your answers, specify only the data for FY 2022-23, and only mention the answer along with the unit mentioned in each query. Avoid extraneous output. Do not make assumptions and be as accurate as possible.",
#         model="gpt-3.5-turbo",
#         tools=[{"type": "file_search"}],
#     )

#     vector_store_name = params["vector_store_name"]
#     vector_store = client.beta.vector_stores.create(name=str(vector_store_name))
#     pdf_file_path = params["pdf_file_path"]

#     file_paths = [str(pdf_file_path)]
#     file_streams = [open(file_path, "rb") for file_path in file_paths]

#     try:
#         file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
#             vector_store_id=vector_store.id, files=file_streams
#         )
#     finally:
#         for stream in file_streams:
#             stream.close()

#     assistant = client.beta.assistants.update(
#         assistant_id=assistant.id,
#         tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}}
#     )

#     excel_file_path = 'questions.xlsx'  # Assuming this file is in the same directory
#     df = pd.read_excel(excel_file_path, engine='openpyxl')  # Specify the engine

#     # Define the output directory
#     output_dir = "output"

#     # Ensure that the output directory exists, if not create it
#     if not os.path.exists(output_dir):
#         os.makedirs(output_dir)

#     # Function to run on queries present in the column
#     def get_answer(question, section):
#         thread = client.beta.threads.create(
#             messages=[
#                 {"role": "user", "content": question}
#             ]
#         )
#         run = client.beta.threads.runs.create_and_poll(
#             thread_id=thread.id, assistant_id=assistant.id
#         )
#         messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))

#         if not messages:
#             return "No response received."

#         message_content = messages[0].content[0].text
#         annotations = message_content.annotations
#         citations = []
#         for index, annotation in enumerate(annotations):
#             message_content.value = message_content.value.replace(annotation.text, f"[{index}]")
#             if file_citation := getattr(annotation, "file_citation", None):
#                 cited_file = client.files.retrieve(file_citation.file_id)
#                 citations.append(f"[{index}] {cited_file.filename}")
#         answer = message_content.value + "\n" + "\n".join(citations)
#         return answer

#     tqdm.pandas()
#     df['Answer'] = df.progress_apply(lambda row: get_answer(row['Data Points'], row['Section/ Point']), axis=1)

#     # Clear the output directory
#     for f in os.listdir(output_dir):
#         os.remove(os.path.join(output_dir, f))

#     # Modify the code where the Excel files are saved to include the output directory
#     grouped = df.groupby('Area of Analysis')
#     for category, group_df in grouped:
#         file_name = os.path.join(output_dir, f"{category}.xlsx")  # Include the output directory
#         group_df.to_excel(file_name, index=False)

#     output_file = os.path.join(output_dir, "Ragresults.xlsx")  # Include the output directory
#     df.to_excel(output_file, index=False)

#     print("Processing complete")

# if __name__ == "__main__":
#     main()
