"use client";

import { useState, useRef, useEffect } from "react";

interface PatentFile {
  name: string;
  size: number;
  type: string;
  lastModified: number;
}

export default function PatentApp() {
  const [uploadedFiles, setUploadedFiles] = useState<PatentFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load existing files on component mount
  useEffect(() => {
    const loadExistingFiles = async () => {
      try {
        const response = await fetch("/api/upload-patents");
        if (response.ok) {
          const result = await response.json();
          setUploadedFiles(result.files || []);
        }
      } catch (error) {
        console.error("Error loading existing files:", error);
      } finally {
        setIsLoading(false);
      }
    };

    loadExistingFiles();
  }, []);

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    setIsUploading(true);
    setUploadStatus("Uploading files...");

    try {
      const formData = new FormData();
      Array.from(files).forEach((file) => {
        formData.append("patents", file);
      });

      const response = await fetch("/api/upload-patents", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        setUploadedFiles((prev) => [...prev, ...result.files]);
        setUploadStatus(`Successfully uploaded ${files.length} file(s)`);
      } else {
        setUploadStatus("Upload failed. Please try again.");
      }
    } catch (error) {
      setUploadStatus("Upload failed. Please try again.");
      console.error("Upload error:", error);
    } finally {
      setIsUploading(false);
      setTimeout(() => setUploadStatus(""), 3000);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleFileUpload(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  return (
    <div className="min-h-screen bg-gradient-to-br dark:from-gray-900 dark:to-gray-800">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <header className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">
            Patent RAG System
          </h1>
          <p className="text-lg text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
            Upload patent documents to build your knowledge base for intelligent question-answering using RAG and Multimodal LLMs
          </p>
        </header>

        {/* Upload Section */}
        <div className="max-w-4xl mx-auto mb-12">
          <div
            className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 text-center hover:border-blue-400 dark:hover:border-blue-500 transition-colors cursor-pointer"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="space-y-4">
              <div className="text-6xl text-gray-400 dark:text-gray-500">
                📄
              </div>
              <div>
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                  Upload Patent Documents
                </h3>
                <p className="text-gray-600 dark:text-gray-300 mb-4">
                  Drag and drop your patent PDF files here, or click to browse
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Supported formats: PDF • Max size: 10MB per file
                </p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf"
                className="hidden"
                onChange={(e) => handleFileUpload(e.target.files)}
              />
              <button
                className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition-colors"
                disabled={isUploading}
              >
                {isUploading ? "Uploading..." : "Choose Files"}
              </button>
            </div>
          </div>

          {/* Upload Status */}
          {uploadStatus && (
            <div className={`mt-4 p-3 rounded-lg text-center ${
              uploadStatus.includes("Successfully") 
                ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
            }`}>
              {uploadStatus}
            </div>
          )}
        </div>

        {/* Uploaded Files Section */}
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-6">
            Patent Documents ({uploadedFiles.length})
          </h2>
          
          {isLoading ? (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="mt-2 text-gray-600 dark:text-gray-300">Loading files...</p>
            </div>
          ) : uploadedFiles.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {uploadedFiles.map((file, index) => (
                <div
                  key={index}
                  className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-md border border-gray-200 dark:border-gray-700 hover:shadow-lg transition-shadow"
                >
                  <div className="flex items-start space-x-3">
                    <div className="text-2xl">📄</div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {file.name}
                      </h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {formatFileSize(file.size)}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {new Date(file.lastModified).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
              <div className="text-4xl text-gray-400 dark:text-gray-500 mb-4">📁</div>
              <p className="text-gray-600 dark:text-gray-300">
                No patent documents uploaded yet. Upload your first document above to get started.
              </p>
            </div>
          )}
        </div>

        {/* Features Section */}
        <div className="max-w-4xl mx-auto mt-16">
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-8 text-center">
            System Features
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="text-4xl mb-4">🤖</div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                RAG Technology
              </h3>
              <p className="text-gray-600 dark:text-gray-300 text-sm">
                Retrieval-Augmented Generation for accurate patent analysis
              </p>
            </div>
            <div className="text-center">
              <div className="text-4xl mb-4">🧠</div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                Multimodal LLMs
              </h3>
              <p className="text-gray-600 dark:text-gray-300 text-sm">
                Advanced language models for text and image understanding
              </p>
            </div>
            <div className="text-center">
              <div className="text-4xl mb-4">💬</div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                Q&A Interface
              </h3>
              <p className="text-gray-600 dark:text-gray-300 text-sm">
                Ask intelligent questions about your patent documents
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
