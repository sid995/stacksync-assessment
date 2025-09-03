import { useState } from 'react';
import axios, { AxiosError } from 'axios';

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';
console.log(DEFAULT_API_URL);

interface ExecutionResult {
  result: unknown;
  stdout: string;
}

interface ApiErrorResponse {
  error: string;
}

interface ExampleScript {
  title: string;
  description: string;
  code: string;
}

const examples: ExampleScript[] = [
  {
    title: 'Simple Hello World',
    description: 'Basic function that returns a JSON object',
    code: `def main():
    return {"message": "Hello, World!", "status": "success"}`
  },
  {
    title: 'Math Operations with Print',
    description: 'Demonstrates both stdout capture and return values',
    code: `def main():
    print("Starting calculations...")
    
    numbers = [1, 2, 3, 4, 5]
    total = sum(numbers)
    average = total / len(numbers)
    
    print(f"Numbers: {numbers}")
    print(f"Sum: {total}")
    print(f"Average: {average}")
    
    return {
        "numbers": numbers,
        "sum": total,
        "average": average,
        "operation": "math_operations"
    }`
  },
  {
    title: 'Using NumPy and Pandas',
    description: 'Shows usage of available libraries',
    code: `import numpy as np
import pandas as pd

def main():
    print("Creating sample data...")
    
    # Create sample data with numpy
    data = np.random.rand(5, 3)
    print(f"Random data shape: {data.shape}")
    
    # Create DataFrame with pandas
    df = pd.DataFrame(data, columns=['A', 'B', 'C'])
    print("DataFrame created:")
    print(df.to_string())
    
    return {
        "data_shape": data.shape,
        "column_means": df.mean().to_dict(),
        "row_count": len(df),
        "library_test": "success"
    }`
  },
  {
    title: 'Error Handling Example',
    description: 'Shows how errors are handled',
    code: `def main():
    print("Testing error handling...")
    
    try:
        result = 10 / 0  # This will cause an error
    except ZeroDivisionError as e:
        print(f"Caught error: {e}")
        return {
            "error_handled": True,
            "error_type": "ZeroDivisionError",
            "message": "Division by zero was handled gracefully"
        }
    
    return {"error_handled": False}`
  }
];

function App() {
  const [script, setScript] = useState<string>('');
  const [apiUrl, setApiUrl] = useState<string>(DEFAULT_API_URL);
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const executeScript = async (): Promise<void> => {
    if (!script.trim()) {
      setError('Please enter a Python script');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await axios.post<ExecutionResult>(`${apiUrl}/execute`, {
        script: script
      }, {
        headers: {
          'Content-Type': 'application/json'
        },
        timeout: 15000 // 15 second timeout
      });

      setResult(response.data);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const axiosError = err as AxiosError<ApiErrorResponse>;
        
        if (axiosError.response) {
          const errorData = axiosError.response.data;
          setError(errorData?.error || 'Server error occurred');
        } else if (axiosError.request) {
          setError('Could not connect to the API. Please check the URL and try again.');
        } else {
          setError('An unexpected error occurred: ' + axiosError.message);
        }
      } else {
        const unknownError = err as Error;
        setError('An unexpected error occurred: ' + unknownError.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const clearScript = (): void => {
    setScript('');
    setResult(null);
    setError(null);
  };

  const tryExample = (exampleCode: string): void => {
    setScript(exampleCode);
    setResult(null);
    setError(null);
  };

  return (
    <div className="container">
      <div className="header">
        <h1>🐍 Python Code Executor</h1>
        <p>Execute Python scripts safely in a sandboxed environment</p>
      </div>

      <div className="editor-section">
        <h2>📝 Code Editor</h2>
        
        <div className="form-group">
          <label htmlFor="api-url">API Endpoint URL:</label>
          <input
            id="api-url"
            type="text"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            placeholder="http://localhost:8080"
            className="url-input"
          />
        </div>

        <div className="form-group">
          <label htmlFor="script-input">Python Script (must contain a main() function):</label>
          <textarea
            id="script-input"
            value={script}
            onChange={(e) => setScript(e.target.value)}
            placeholder="def main():&#10;    return {'message': 'Hello, World!'}"
            className="code-textarea"
          />
        </div>

        <div className="form-group">
          <button onClick={executeScript} disabled={loading} className="execute-btn">
            {loading ? '⏳ Executing...' : '▶️ Execute Script'}
          </button>
          <button onClick={clearScript} className="clear-btn">
            🗑️ Clear
          </button>
        </div>
      </div>

      {(result || error) && (
        <div className="result-section">
          <h2>📊 Execution Result</h2>
          
          {error && (
            <div className="result-box result-error">
              <strong>❌ Error:</strong><br />
              {error}
            </div>
          )}
          
          {result && (
            <>
              <div className="result-box result-success">
                <strong>✅ Return Value:</strong><br />
                {JSON.stringify(result.result, null, 2)}
              </div>
              
              {result.stdout && (
                <div className="result-box">
                  <strong>📤 Standard Output:</strong><br />
                  {result.stdout}
                </div>
              )}
            </>
          )}
        </div>
      )}

      <div className="examples-section">
        <h2>💡 Example Scripts</h2>
        
        {examples.map((example, index) => (
          <div key={index} className="example">
            <h3>{example.title}</h3>
            <p>{example.description}</p>
            <div className="example-code">
              {example.code}
            </div>
            <button onClick={() => tryExample(example.code)} className="try-btn">
              Try This Example
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;