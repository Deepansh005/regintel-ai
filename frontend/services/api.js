const BASE_URL = "http://localhost:8000";

export const uploadDocuments = async (oldFile, newFile) => {
  const formData = new FormData();
  formData.append("old_file", oldFile);
  formData.append("new_file", newFile);

  const response = await fetch(`${BASE_URL}/upload-documents`, {
    method: "POST",
    body: formData,
  });

  return response.json();
};