"use client";

import { useState, useCallback } from "react";

const API_URL = "http://localhost:8000";

interface Case {
  case_id: string;
  customer_id: string;
  fields: Record<string, string>;
  field_count: number;
  status: string;
  created_at: string;
}

export default function LumaDashboard() {
  const [cases, setCases] = useState<Case[]>([]);
  const [uploading, setUploading] = useState(false);
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [customerId] = useState("draper-mortuary-ontario"); // Default for demo

  // Upload a document and process it
  const handleUpload = useCallback(async (file: File) => {
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_URL}/api/ingest?customer_id=${customerId}`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        alert(`Error: ${err.detail}`);
        return;
      }

      const result = await res.json();
      setCases((prev) => [result, ...prev]);
      setSelectedCase(result);
    } catch (e) {
      alert("Could not connect to LUMA API. Make sure the backend is running on port 8000.");
    } finally {
      setUploading(false);
    }
  }, [customerId]);

  // Drag and drop
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  }, [handleUpload]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  };

  // Confidence color
  const confidenceColor = (fieldName: string) => {
    const highConfidence = ["deceased_name", "date_of_birth", "date_of_death", "disposition_method"];
    const medConfidence = ["address", "city", "state", "next_of_kin_name"];
    if (highConfidence.includes(fieldName)) return "bg-green-100 text-green-800";
    if (medConfidence.includes(fieldName)) return "bg-yellow-100 text-yellow-800";
    return "bg-gray-100 text-gray-700";
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-8 py-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">L</span>
          </div>
          <div>
            <h1 className="text-lg font-semibold text-gray-900">LUMA</h1>
            <p className="text-xs text-gray-500">Learning Universal Machine Architecture</p>
          </div>
          <div className="ml-auto text-sm text-gray-500">
            Customer: <span className="font-medium text-gray-700">{customerId}</span>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-8 py-8">
        <div className="grid grid-cols-3 gap-8">

          {/* Left: Upload + Case List */}
          <div className="col-span-1 space-y-6">

            {/* Upload Zone */}
            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              className="border-2 border-dashed border-blue-300 rounded-xl p-8 text-center bg-white hover:border-blue-400 transition-colors cursor-pointer"
            >
              <div className="text-4xl mb-3">📄</div>
              <p className="text-sm font-medium text-gray-700">
                {uploading ? "Processing..." : "Drop a document here"}
              </p>
              <p className="text-xs text-gray-400 mt-1">PDF, PNG, JPG, TIFF accepted</p>
              <label className="mt-4 inline-block">
                <input
                  type="file"
                  className="hidden"
                  accept=".pdf,.png,.jpg,.jpeg,.tiff,.csv"
                  onChange={handleFileInput}
                />
                <span className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg cursor-pointer hover:bg-blue-700">
                  {uploading ? "⏳ Processing..." : "Choose File"}
                </span>
              </label>
            </div>

            {/* Case List */}
            <div className="bg-white rounded-xl border border-gray-200">
              <div className="px-4 py-3 border-b border-gray-100">
                <h2 className="text-sm font-semibold text-gray-700">
                  Processed Cases ({cases.length})
                </h2>
              </div>
              <div className="divide-y divide-gray-100">
                {cases.length === 0 && (
                  <div className="px-4 py-8 text-center text-sm text-gray-400">
                    No cases yet. Upload a document to start.
                  </div>
                )}
                {cases.map((c) => (
                  <button
                    key={c.case_id}
                    onClick={() => setSelectedCase(c)}
                    className={`w-full px-4 py-3 text-left hover:bg-gray-50 transition-colors ${
                      selectedCase?.case_id === c.case_id ? "bg-blue-50" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-800">
                          {c.fields?.deceased_name || "Unknown"}
                        </p>
                        <p className="text-xs text-gray-400">
                          {c.fields?.date_of_death || "Date unknown"}
                        </p>
                      </div>
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                        {c.field_count} fields
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Right: Case Detail */}
          <div className="col-span-2">
            {selectedCase ? (
              <div className="bg-white rounded-xl border border-gray-200">
                <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-gray-900">
                      {selectedCase.fields?.deceased_name || "Case Details"}
                    </h2>
                    <p className="text-xs text-gray-400">
                      Case ID: {selectedCase.case_id?.slice(0, 8)}...
                    </p>
                  </div>
                  <span className="text-xs bg-green-100 text-green-700 px-3 py-1 rounded-full font-medium">
                    ✓ {selectedCase.field_count} fields extracted
                  </span>
                </div>

                <div className="p-6">
                  <p className="text-xs text-gray-500 mb-4">
                    🟢 Green = high confidence auto-fill &nbsp;|&nbsp;
                    🟡 Yellow = review recommended &nbsp;|&nbsp;
                    ⚪ Gray = lower confidence
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries(selectedCase.fields).map(([field, value]) => (
                      <div key={field} className={`p-3 rounded-lg ${confidenceColor(field)}`}>
                        <p className="text-xs font-medium uppercase tracking-wide opacity-60 mb-1">
                          {field.replace(/_/g, " ")}
                        </p>
                        <p className="text-sm font-semibold">{String(value)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 h-64 flex items-center justify-center">
                <div className="text-center text-gray-400">
                  <div className="text-4xl mb-2">👆</div>
                  <p className="text-sm">Upload a document or select a case to view extracted fields</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
