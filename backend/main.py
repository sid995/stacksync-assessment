import ast
import os
import json
import subprocess
import logging
from typing import Tuple, Optional, Any

from flask import Flask, request, jsonify
from flask_cors import CORS

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

NSJAIL_CONFIG_PATH = "/etc/nsjail.cfg"
IS_CLOUD = os.environ.get("BUILD") == "cloud"
SCRIPT_TIMEOUT = int(os.environ.get("SCRIPT_TIMEOUT", "10"))
MAX_SCRIPT_SIZE = int(os.environ.get("MAX_SCRIPT_SIZE", "10000"))  # 10KB max

SCRIPT_PATH = "/sandbox/tmp/script.py" if IS_CLOUD else "/tmp/script.py"

def validate_script(script_content: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that the script contains a main() function and is syntactically correct.
    Returns (is_valid, error_message)
    """
    if len(script_content) > MAX_SCRIPT_SIZE:
        return False, f"Script too large. Maximum size is {MAX_SCRIPT_SIZE} characters."
    
    dangerous_patterns = [
        'import os', 'import sys', 'import subprocess', 'import shutil',
        '__import__', 'eval(', 'exec(', 'compile(',
        'open(', 'file(', 'input(', 'raw_input(',
        'exit(', 'quit(', 'reload('
    ]
    
    for pattern in dangerous_patterns:
        if pattern in script_content:
            return False, f"Dangerous operation detected: {pattern}"
    
    try:
        tree = ast.parse(script_content)
    except SyntaxError as e:
        return False, f"Syntax error in script: {str(e)}"
    
    has_main = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            has_main = True
            break
    
    if not has_main:
        return False, "Script must contain a main() function"
    
    return True, None

def execute_script_safely(script_content: str) -> Tuple[Optional[Any], str, Optional[str]]:
    """
    Execute the script safely using nsjail and return the result and stdout.
    Returns (result, stdout, error_message)
    """
    script_path = SCRIPT_PATH
    
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
        with open(script_path, 'w') as f:
            f.write(wrapper_script)

        if IS_CLOUD:
            cmd = [
                "nsjail",
                "--config", NSJAIL_CONFIG_PATH,
                "--"
            ]
        else:
            cmd = ["python3", script_path]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT
        )

        if result.returncode != 0:
            logger.warning(f"Script execution failed with return code {result.returncode}: {result.stderr}")
            return None, result.stderr, f"Script execution failed: {result.stderr}"

        output = result.stdout

        try:
            if "__STDOUT_START__" in output and "__STDOUT_END__" in output:
                index_start = output.find("__STDOUT_START__") + len("__STDOUT_START__\n")
                index_end = output.find("__STDOUT_END__")
                captured_stdout = output[index_start:index_end].rstrip("\n")
            else:
                captured_stdout = ""

            if "__RESULT_START__" in output and "__RESULT_END__" in output:
                index_start = output.find("__RESULT_START__") + len("__RESULT_START__\n")
                index_end = output.find("__RESULT_END__")
                result_json = output[index_start:index_end].strip()

                try:
                    result_data = json.loads(result_json)
                    return result_data, captured_stdout, None
                except json.JSONDecodeError:
                    return None, captured_stdout, f"main() function must return a JSON-serializable value. Got: {result_json}"

            elif "__ERROR_START__" in output and "__ERROR_END__" in output:
                index_start = output.find("__ERROR_START__") + len("__ERROR_START__\n")
                index_end = output.find("__ERROR_END__")
                error_message = output[index_start:index_end].strip()
                return None, captured_stdout, error_message

            else:
                return None, captured_stdout, f"Could not parse script output. Output: {output}"

        except Exception as e:
            logger.error(f"Error parsing script output: {str(e)}")
            return None, None, f"Error parsing script output: {str(e)}"
    except subprocess.TimeoutExpired:
        logger.warning("Script execution timed out")
        return None, None, "Script execution timed out"
    except Exception as e:
        logger.error(f"Unexpected error during script execution: {str(e)}")
        return None, None, f"Unexpected error: {str(e)}"
    finally:
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
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        data = request.get_json()
        
        if 'script' not in data:
            return jsonify({"error": "Missing 'script' field in request body"}), 400

        script_content = data['script']

        if not isinstance(script_content, str) or not script_content.strip():
            return jsonify({"error": "Script must be a non-empty string"}), 400

        is_valid, error_msg = validate_script(script_content)
        if not is_valid:
            return jsonify({"error": error_msg}), 400

        result, stdout, error = execute_script_safely(script_content)

        if error:
            logger.warning(f"Script execution error: {error}")
            return jsonify({"error": error}), 500

        logger.info("Script executed successfully")
        return jsonify({
            "result": result,
            "stdout": stdout
        })

    except Exception as e:
        logger.error(f"Internal server error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "service": "Python Code Execution API",
        "environment": "cloud" if IS_CLOUD else "local",
        "version": "1.0.0",
        "nsjail_enabled": IS_CLOUD
    })

@app.route('/', methods=['GET'])
def root():
    """Root endpoint with API information."""
    return jsonify({
        "message": "Python Code Execution API",
        "description": "Execute arbitrary Python scripts safely",
        "version": "1.0.0",
        "environment": "cloud" if IS_CLOUD else "local",
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
        },
        "limits": {
            "max_script_size": MAX_SCRIPT_SIZE,
            "execution_timeout": SCRIPT_TIMEOUT,
            "allowed_libraries": ["pandas", "numpy", "json", "math", "random", "datetime"]
        }
    })

@app.errorhandler(413)
def too_large(e):
    """Handle request too large errors."""
    return jsonify({"error": "Request too large"}), 413

@app.errorhandler(429)
def too_many_requests(e):
    """Handle rate limiting errors."""
    return jsonify({"error": "Too many requests"}), 429

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting Python Code Execution API on port {port}")
    logger.info(f"Environment: {'cloud' if IS_CLOUD else 'local'}")
    logger.info(f"Debug mode: {debug_mode}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)