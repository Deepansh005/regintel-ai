const BASE_URL = "http://127.0.0.1:8000";

export const uploadDocuments = async (oldFile, newFile, policyFile) => {
  const formData = new FormData();
  formData.append("old_file", oldFile);
  formData.append("new_file", newFile);
  if (policyFile) {
    formData.append("policy_file", policyFile);
  }

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
