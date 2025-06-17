import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";

const SecurityTools = () => {
  const [uploadStatus, setUploadStatus] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);

  const onDrop = useCallback(async (acceptedFiles) => {
    const formData = new FormData();
    acceptedFiles.forEach((file) => formData.append("file", file));

    setUploadStatus("Uploading...");
    try {
      const res = await fetch("/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error("Upload failed");

      const data = await res.json();
      setAnalysisResult(data);
      setUploadStatus("Upload and analysis complete");
    } catch (err) {
      console.error(err);
      setUploadStatus("Upload failed");
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  return (
    <div className="p-6 text-white">
      <h1 className="text-3xl font-bold mb-6">Security Tools: File Analysis</h1>

      <div
        {...getRootProps()}
        className={`border-dashed border-4 rounded-lg p-10 text-center transition-colors duration-300 ${
          isDragActive ? "border-cyan-400 bg-zinc-800" : "border-zinc-600 bg-zinc-900"
        }`}
      >
        <input {...getInputProps()} />
        {isDragActive ? (
          <p>Drop the files here...</p>
        ) : (
          <p>Drag and drop files here, or click to browse.</p>
        )}
      </div>

      {uploadStatus && <p className="mt-4 text-cyan-400">{uploadStatus}</p>}

      {analysisResult && (
        <div className="mt-6 bg-zinc-800 p-4 rounded-lg overflow-auto">
          <h2 className="text-xl font-semibold mb-2">Analysis Result:</h2>
          <pre className="whitespace-pre-wrap text-sm text-zinc-300">
            {JSON.stringify(analysisResult, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

export default SecurityTools;
