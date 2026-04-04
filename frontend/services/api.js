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