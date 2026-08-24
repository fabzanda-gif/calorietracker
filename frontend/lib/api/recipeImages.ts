import { supabase } from "@/lib/supabase/client";

const RECIPE_IMAGE_BUCKET = "recipe-images";

function extensionForFile(file: File): string {
  const mime = file.type.toLowerCase();

  if (mime === "image/png") {
    return "png";
  }

  if (mime === "image/webp") {
    return "webp";
  }

  return "jpg";
}

export async function uploadRecipeImage(
  file: File,
  userId: string,
): Promise<string> {
  const ext = extensionForFile(file);

  const objectPath =
    `${userId}/${crypto.randomUUID()}.${ext}`;

  const { error } = await supabase.storage
    .from(RECIPE_IMAGE_BUCKET)
    .upload(
      objectPath,
      file,
      {
        contentType:
          file.type || `image/${ext}`,
        cacheControl: "3600",
        upsert: false,
      },
    );

  if (error) {
    throw error;
  }

  const { data } = supabase.storage
    .from(RECIPE_IMAGE_BUCKET)
    .getPublicUrl(objectPath);

  const publicUrl =
    data.publicUrl?.trim();

  if (!publicUrl) {
    throw new Error(
      "Impossibile ottenere la URL pubblica della foto.",
    );
  }

  return publicUrl;
}
