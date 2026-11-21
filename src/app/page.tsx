import { connection } from "next/server";
import { Suspense } from "react";
import { UploadForm } from "./upload-form";

export const metadata = { title: "Utwórz e-formularz z pliku" };

// The size limit is runtime config (same env as the API), so read it per request.
async function Upload() {
  await connection();
  const maxSizeMb = Number(process.env.AUTOFORMULARZ_MAX_UPLOAD_MB) || 20;
  return <UploadForm maxSizeMb={maxSizeMb} />;
}

export default function Home() {
  return (
    <Suspense fallback={<div className="flex-1 bg-page" />}>
      <Upload />
    </Suspense>
  );
}
