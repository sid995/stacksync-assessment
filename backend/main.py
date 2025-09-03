import ast
import os
import json
import subprocess

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

NSJAIL_CONFIG_PATH = "/etc/nsjail.cfg"
IS_CLOUD = os.environ.get("BUILD") == "cloud"
SCRIPT_TIMEOUT = 10

SCRIPT_PATH = "/sandbox/tmp/script.py" if IS_CLOUD else "/tmp/script.py"


def validate_script(script_content):
    """
    Validate that the script contains a main() function and is syntactically correct.
    Returns (is_valid, error_message)
    """

    # parse script to check syntax
    try:
        tree = ast.parse(script_content)
    except SyntaxError as e:
        return False, f"Syntax error in script: {str(e)}"

    # check if main() exists
    has_main = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            has_main = True
            break

    if not has_main:
        return False, "Script must contain a main() function"

    return True, None


def execute_script_safely(script_content):
    """
    Execute the script safely using nsjail and return the result and stdout.
    Returns (result, stdout, error_message)
    """

    script_path = SCRIPT_PATH

    # Create wrapper script that captures both stdout and return value
    try:
        wrapper_script = f'''
import sys
import json
import io
from contextlib import redirect_stdout

# Original script
{script_content}

# Execution wrapper
if __name__ == "__main__":
    try:
        # capture stdout
        stdout_capture = io.StringIO()

        with redirect_stdout(stdout_capture):
            result = main()

        # capture stdout
        captured_stdout = stdout_capture.getvalue()

        # print result in structured way
        print("__STDOUT_START__")
        print(captured_stdout, end="")
        print("__STDOUT_END__")

        print("__RESULT_START__")
        print(json.dumps(result))
        print("__RESULT_END__")

    except Exception as e:
        print("__ERROR_START__")
        print(f"Error in main() function: {{str(e)}}")
        print("__ERROR_END__")
'''
        # Write the wrapper script to file
        with open(script_path, 'w') as f:
            f.write(wrapper_script)

        # Prepare execution command
        if IS_CLOUD:
            # Use nsjail in cloud environment for security
            cmd = [
                "nsjail",
                "--config", NSJAIL_CONFIG_PATH,
                "--"
            ]
        else:
            # For local testing, run directly (less secure but for development)
            cmd = ["python3", script_path]

        # Execute the script
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT
        )

        if result.returncode != 0:
            return None, result.stderr, f"Script execution failed: {result.stderr}"

        output = result.stdout

        # parse content
        try:
            # extract stdout
            if "__STDOUT_START__" in output and "__STDOUT_END__" in output:
                index_start = output.find("__STDOUT_START__") + len("__STDOUT_START__\n")
                index_end = output.find("__STDOUT_END__")
                captured_stdout = output[index_start:index_end].rstrip("\n")
            else:
                captured_stdout = ""

            # extract result
            if "__RESULT_START__" in output and "__RESULT_END__" in output:
                index_start = output.find("__RESULT_START__") + len("__RESULT_START__\n")
                index_end = output.find("__RESULT_END__")
                result_json = output[index_start:index_end].strip()

                try:
                    result_data = json.loads(result_json)
                    return result_data, captured_stdout, None
                except json.JSONDecodeError:
                    return None, captured_stdout, f"main() function must return a JSON-serializable value. Got: {result_json}"

            # check for errors
            elif "__ERROR_START__" in output and "__ERROR_END__" in output:
                index_start = output.find("__ERROR_START__") + len("__ERROR_START__\n")
                index_end = output.find("__ERROR_END__")
                error_message = output[index_start:index_end].strip()
                return None, captured_stdout, error_message

            else:
                return None, captured_stdout, f"Could not parse script output. Output: {output}"

        except Exception as e:
            return None, None, f"Error parsing script output: {str(e)}"
    except subprocess.TimeoutExpired:
        return None, None, "Script execution timed out"
    except Exception as e:
        return None, None, f"Unexpected error: {str(e)}"
    finally:
        # cleanup code
        if os.path.exists(script_path):
            try:
                os.remove(script_path)
            except:
                pass


@app.route("/execute", methods=["POST"])
def execute():
    """
    Execute a Python script and return the result of main() function.

    Expected JSON body:
    {
        "script": "def main(): return {'message': 'Hello World'}"
    }

    Returns:
    {
        "result": <return value of main()>,
        "stdout": <captured stdout from script>
    }
    """
    try:
        # Validate request content type
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()

        # Validate required fields
        if 'script' not in data:
            return jsonify({"error": "Missing 'script' field in request body"}), 400

        script_content = data['script']

        # Validate script content
        if not isinstance(script_content, str) or not script_content.strip():
            return jsonify({"error": "Script must be a non-empty string"}), 400

        # Validate script syntax and structure
        is_valid, error_msg = validate_script(script_content)
        if not is_valid:
            return jsonify({"error": error_msg}), 400

        # Execute script safely
        result, stdout, error = execute_script_safely(script_content)

        if error:
            return jsonify({"error": error}), 500

        return jsonify({
            "result": result,
            "stdout": stdout
        })

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "Python Code Execution API",
        "environment": "cloud" if IS_CLOUD else "local"
    })


@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API information."""
    return jsonify({
        "message": "Python Code Execution API",
        "description": "Execute arbitrary Python scripts safely",
        "endpoints": {
            "/": "GET - API information",
            "/execute": "POST - Execute Python script with main() function",
            "/health": "GET - Health check"
        },
        "usage": {
            "method": "POST",
            "url": "/execute",
            "content_type": "application/json",
            "body": {
                "script": "def main(): return {'message': 'Hello World'}"
            }
        }
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)