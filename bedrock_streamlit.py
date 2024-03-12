import json
import base64
import logging
import boto3
import streamlit as st

from botocore.exceptions import ClientError, NoCredentialsError


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def images_process(image_file):
    image_string = base64.b64encode(image_file.read()).decode('utf8')
    return image_string

def image_update():
    st.session_state.image_update = True

def stream_multi_modal_prompt(bedrock_runtime, model_id, system_message, messages, max_tokens, temperature, top_p, top_k):
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system":  system_message,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "messages": messages
    })

    response = bedrock_runtime.invoke_model_with_response_stream(body=body, modelId=model_id)

    for event in response.get("body"):
        chunk = json.loads(event["chunk"]["bytes"])
        if chunk['type'] == 'content_block_delta':
            if chunk['delta']['type'] == 'text_delta':
                yield chunk['delta']['text']
                # print(chunk['delta']['text'], end="")
        # if chunk['type'] == 'message_delta':
        #     print(f"\nStop reason: {chunk['delta']['stop_reason']}")
        #     print(f"Stop sequence: {chunk['delta']['stop_sequence']}")
        #     print(f"Output tokens: {chunk['usage']['output_tokens']}")

# def clear_history():
#     st.session_state.messages = []
#     st.empty()
#     st.session_state["file_uploader_key"] += 1
#     st.rerun()

def get_bedrock_runtime_client(aws_access_key=None, aws_secret_key=None, aws_region=None):
    try:
        if aws_access_key and aws_secret_key and aws_region:
            bedrock_runtime = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
        else:
            bedrock_runtime = boto3.client('bedrock-runtime')
    except ClientError as e:
        # Handle errors returned by the AWS service
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"AWS service returned an error: {error_code} - {error_message}")
        raise
    except NoCredentialsError:
        # Handle the case where credentials are missing
        print("Unable to retrieve AWS credentials, please check your credentials configuration.")
        raise
    except Exception as e:
        # Handle any other unknown exceptions
        print(f"An unknown error occurred: {str(e)}")
        raise
    return bedrock_runtime

def main():
    # App title
    st.set_page_config(page_title="Bedrock-Claude 💬")

    with st.sidebar:
        col1, col2 = st.columns([1,3])
        with col1:
            st.image('./utils/logo.png')
        with col2:
            st.title("AWS-Bedrock-Claude")

        with st.expander('AWS Credentials', expanded=False):
            aws_access_key = st.text_input('AWS Access Key', "", type="password")
            aws_secret_key = st.text_input('AWS Secret Key', "", type="password")
            aws_region = st.text_input('AWS Region', "")

        model_id = st.selectbox('Choose a Model', ('Anthropic Claude-V3', 'Anthropic Claude-V2.1', 'Anthropic Claude-V2', 'Anthropic Claude-Instant-V1.2'), label_visibility="collapsed")
        model_id = {
            'Anthropic Claude-V2': 'anthropic.claude-v2',
            'Anthropic Claude-V2.1': 'anthropic.claude-v2:1',
            'Anthropic Claude-Instant-V1.2': 'anthropic.claude-instant-v1',
            'Anthropic Claude-V3': 'anthropic.claude-3-sonnet-20240229-v1:0'
        }.get(model_id, model_id)

        with st.expander('System Prompt', expanded=False):
            system_prompt = st.text_area(
                "System prompt", 
                "You are an helpful, harmless, and honest AI assistant. "
                "Your goal is to provide informative and substantive responses to queries while avoiding potential harms.", 
                label_visibility="collapsed"
            )

        with st.expander('Model Parameters', expanded=False):
            max_new_tokens= st.number_input(
                min_value=10,
                max_value=4096,
                step=10,
                value=1024,
                label="Number of tokens to generate",
                key="max_new_token"
            )
            col1, col2 = st.columns([4,1])
            with col1:
                temperature = st.slider(
                    min_value=0.1,
                    max_value=1.0,
                    step=0.1,
                    value=0.5,
                    label="Temperature",
                    key="temperature"
                )
                top_p = st.slider(
                    min_value=0.0,
                    max_value=1.0,
                    step=0.1,
                    value=1.0,
                    label="Top P",
                    key="top_p"
                )
                top_k = st.slider(
                    min_value=0,
                    max_value=500,
                    step=1,
                    value=250,
                    label="Top K",
                    key="top_k"
                )

        if "file_uploader_key" not in st.session_state:
            st.session_state["file_uploader_key"] = 0
            
        if "claude-3" in model_id:
            image = st.file_uploader("Image Query", accept_multiple_files=True, key=st.session_state["file_uploader_key"], on_change=image_update, help='Claude-V3 only', disabled=False)
            image_list = []
            for item in image:
                st.image(item, caption=item.name)
                image_list.append({"type": "image", "source": {"type": "base64", "media_type": item.type, "data": images_process(item)}})
        else:
            image = st.file_uploader("Upload images", help='Claude-V3 only', disabled=True)
    
        # st.sidebar.button("Clear history", type="primary", on_click=clear_history)
        if st.sidebar.button("Clear history", type="primary"):
            st.session_state.messages = []
            st.empty()
            st.session_state["file_uploader_key"] += 1
            st.rerun()

    with st.chat_message("assistant", avatar="./utils/assistant.png"):
        st.write("I am an AI chatbot powered by Amazon Bedrock Claude, what can I do for you？💬")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Initialize image track recorder
    if "image_update" not in st.session_state:
        st.session_state.image_update = False

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        if message["role"] == "assistant":
            with st.chat_message(message["role"], avatar="./utils/assistant.png"):
                st.markdown(message["content"][0]["text"])
        else:
            with st.chat_message(message["role"], avatar="./utils/user.png"):
                for item in message["content"]:
                    if item["type"] == "image":
                        image_data = base64.b64decode(item["source"]["data"].encode('utf8'))
                        st.image(image_data, width=50)
                    else:
                        st.markdown(item["text"])

    if query := st.chat_input("Input your message..."):
        # Display user message in chat message container
        with st.chat_message("user", avatar="./utils/user.png"):
            user_content = []
            if st.session_state.image_update:
                for item in image:
                    st.image(item, width=50)
                user_content = image_list
            st.session_state.image_update = False
            st.markdown(query)
        # Add user message to chat history
        user_content.append({"type": "text", "text": query})
        st.session_state.messages.append({"role": "user", "content": user_content})
        # Display assistant response in chat message container
        with st.chat_message("assistant", avatar="./utils/assistant.png"):
            system_message = system_prompt
            messages = st.session_state.messages
            bedrock_runtime = get_bedrock_runtime_client(aws_access_key, aws_secret_key, aws_region)
            with st.spinner('Thinking...'):
                try:
                    response= st.write_stream(stream_multi_modal_prompt(
                        bedrock_runtime, model_id, system_message, messages, max_new_tokens, temperature, top_p, top_k
                        )
                    )
                    assistant_content = [{"type": "text", "text": response}]
                    st.session_state.messages.append({"role": "assistant", "content": assistant_content})
                except ClientError as err:
                    message = err.response["Error"]["Message"]
                    logger.error("A client error occurred: %s", message)
                    print("A client error occured: " + 
                          format(message))

if __name__ == "__main__":
    main()