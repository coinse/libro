from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig
from flask import Flask, request
import json
import argparse

app = Flask(__name__)

@app.route('/', methods=['POST'])
def process_json():
    data = request.get_json()

    # Perform operations on the JSON data
    client_error = True
    if 'text' not in data:
        result = 'There is nothing to predict.'
    else:
        input_prompt = data['text']
        encoded_text = tokenizer.encode(input_prompt, return_tensors="pt").to(0)
        max_new_tokens = data['max_new_tokens'] if 'max_new_tokens' in data else 64
        temp = data['temperature'] if 'temperature' in data else 0.7
        output = model.generate(
            encoded_text,
            max_new_tokens = max_new_tokens,
            do_sample = True,
            temperature = temp,
        )
        result = tokenizer.decode(output[0])
        result = result[len(input_prompt):]
        client_error = False

    # Prepare the response
    response_code = 400 if client_error else 200
    response = {'result': result}

    return json.dumps(response), response_code

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--llm', help='LLM to serve')
    args = parser.parse_args()

    model = AutoModelForCausalLM.from_pretrained(
        args.llm, 
        use_auth_token=True, 
        resume_download=True,
        device_map='auto',
    )
    tokenizer = AutoTokenizer.from_pretrained(args.llm, use_auth_token=True)
    
    app.run(host='0.0.0.0', port=23623)

