const BASE_URL = "http://127.0.0.1:8000";

export const uploadDocuments = async (oldFiles = [], newFiles = [], policyFiles = []) => {
  const formData = new FormData();
  for (const file of oldFiles) formData.append("old_file", file);
  for (const file of newFiles) formData.append("new_file", file);
  for (const file of policyFiles) formData.append("policy_file", file);

  const response = await fetch(`${BASE_URL}/upload-documents`, {
    method: "POST",
    body: formData,
  });

  return response.json();
};

export const fetchTasks = async () => {
  const response = await fetch(`${BASE_URL}/tasks`, {
    method: "GET",
    headers: {
      "Cache-Control": "no-cache",
      Pragma: "no-cache",
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch tasks: ${response.status}`);
  }
  return response.json();
};

export const clearTaskHistory = async () => {
  const response = await fetch(`${BASE_URL}/tasks/clear-history`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(`Failed to clear history: ${response.status}`);
  }

  return response.json();
};

export const deleteOldTasks = async (days = 7) => {
  const response = await fetch(`${BASE_URL}/tasks/delete-old?days=${days}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(`Failed to delete old tasks: ${response.status}`);
  }

  return response.json();
};

export const fetchChunkDetails = async (chunkIds) => {
  const response = await fetch(`${BASE_URL}/chunks/details`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ chunk_ids: chunkIds }),
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch chunk details: ${response.status}`);
  }

  return response.json();
};
