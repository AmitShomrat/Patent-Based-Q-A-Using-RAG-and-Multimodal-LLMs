import { NextRequest, NextResponse } from 'next/server';
import { writeFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const files = formData.getAll('patents') as File[];
    
    if (!files || files.length === 0) {
      return NextResponse.json(
        { error: 'No files provided' },
        { status: 400 }
      );
    }

    // Define the upload directory (rag_inputs folder in the parent directory)
    const uploadDir = path.join(process.cwd(), '..', 'rag_inputs');
    
    // Create directory if it doesn't exist
    if (!existsSync(uploadDir)) {
      await mkdir(uploadDir, { recursive: true });
    }

    const uploadedFiles = [];

    for (const file of files) {
      // Validate file type
      if (file.type !== 'application/pdf') {
        return NextResponse.json(
          { error: `Invalid file type: ${file.name}. Only PDF files are allowed.` },
          { status: 400 }
        );
      }

      // Validate file size (10MB limit)
      const maxSize = 10 * 1024 * 1024; // 10MB
      if (file.size > maxSize) {
        return NextResponse.json(
          { error: `File too large: ${file.name}. Maximum size is 10MB.` },
          { status: 400 }
        );
      }

      // Convert file to buffer
      const bytes = await file.arrayBuffer();
      const buffer = Buffer.from(bytes);

      // Create safe filename (remove special characters)
      const safeFileName = file.name.replace(/[^a-zA-Z0-9.-]/g, '_');
      const filePath = path.join(uploadDir, safeFileName);

      // Write file to disk
      await writeFile(filePath, buffer);

      uploadedFiles.push({
        name: safeFileName,
        originalName: file.name,
        size: file.size,
        type: file.type,
        lastModified: file.lastModified,
        path: filePath
      });
    }

    return NextResponse.json({
      message: `Successfully uploaded ${uploadedFiles.length} file(s)`,
      files: uploadedFiles
    });

  } catch (error) {
    console.error('Upload error:', error);
    return NextResponse.json(
      { error: 'Failed to upload files' },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    // Get list of existing files in rag_inputs directory
    const uploadDir = path.join(process.cwd(), '..', 'rag_inputs');
    
    if (!existsSync(uploadDir)) {
      return NextResponse.json({ files: [] });
    }

    const { readdir, stat } = await import('fs/promises');
    const files = await readdir(uploadDir);
    
    const fileList = await Promise.all(
      files.map(async (fileName) => {
        const filePath = path.join(uploadDir, fileName);
        const stats = await stat(filePath);
        
        return {
          name: fileName,
          size: stats.size,
          type: 'application/pdf',
          lastModified: stats.mtime.getTime(),
          path: filePath
        };
      })
    );

    return NextResponse.json({ files: fileList });

  } catch (error) {
    console.error('Error reading files:', error);
    return NextResponse.json(
      { error: 'Failed to read files' },
      { status: 500 }
    );
  }
}
