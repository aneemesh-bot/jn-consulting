const express = require("express");
const multer = require("multer");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const archiver = require("archiver");
const http = require("http");
const WebSocket = require("ws");
const cors = require("cors");

const app = express();
const port = 3000;

const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

app.use(cors());

const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, "uploads/");
  },
  filename: function (req, file, cb) {
    cb(null, file.originalname);
  },
});

const upload = multer({ storage: storage });

app.use(express.json());

app.post("/run-python", upload.single("pdfFile"), (req, res) => {
  const { vector_store_name } = req.body;
  const pdfFilePath = req.file.path;

  // Clear the output directory
  const outputDir = "output/";
  fs.readdir(outputDir, (err, files) => {
    if (err) throw err;
    for (const file of files) {
      fs.unlink(path.join(outputDir, file), (err) => {
        if (err) throw err;
      });
    }
  });

  const params = {
    vector_store_name: vector_store_name,
    pdf_file_path: pdfFilePath,
  };

  const pythonProcess = spawn("python3", ["script.py"], {
    stdio: ["pipe", "pipe", "pipe"],
  });

  pythonProcess.stdin.write(JSON.stringify(params));
  pythonProcess.stdin.end();

  let result = "";
  pythonProcess.stdout.on("data", (data) => {
    result += data.toString();
    // Forward stdout data to WebSocket clients
    wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(
          JSON.stringify({ type: "progress", message: data.toString() })
        );
      }
    });
  });

  pythonProcess.stderr.on("data", (data) => {
    console.error(`stderr: ${data}`);
    // Forward stderr data to WebSocket clients
    wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(
          JSON.stringify({ type: "error", message: data.toString() })
        );
      }
    });
  });

  pythonProcess.on("close", (code) => {
    if (fs.existsSync(pdfFilePath)) {
      fs.unlink(pdfFilePath, (err) => {
        if (err) {
          console.error(`Error deleting file: ${err}`);
        }
      });
    }

    const outputFiles = fs.readdirSync(outputDir);

    const zipFileName = `${vector_store_name}.zip`;
    const zipStream = fs.createWriteStream(zipFileName);
    const archive = archiver("zip", {
      zlib: { level: 9 },
    });

    zipStream.on("close", () => {
      res.json({ zipFileName });
    });

    archive.pipe(zipStream);
    outputFiles.forEach((file) => {
      archive.file(path.join(outputDir, file), { name: file });
    });
    archive.finalize();
  });
});

wss.on("connection", (ws) => {
  console.log("WebSocket connection opened");

  ws.on("close", () => {
    console.log("WebSocket connection closed");
  });
});

app.get("/download/:zipFileName", (req, res) => {
  const zipFileName = req.params.zipFileName;
  const filePath = path.join(__dirname, zipFileName);
  res.download(filePath, (err) => {
    if (err) {
      console.error(`Error downloading file: ${err}`);
    }
    fs.unlink(filePath, (err) => {
      if (err) {
        console.error(`Error deleting file: ${err}`);
      }
    });
  });
});

server.listen(port, () => {
  console.log(`Server is running on http://localhost:${port}`);
});

// const express = require("express");
// const multer = require("multer");
// const { spawn } = require("child_process");
// const path = require("path");
// const fs = require("fs");
// const archiver = require("archiver");
// const http = require("http");
// const WebSocket = require("ws");

// const app = express();
// const port = 3000;

// const server = http.createServer(app);
// const wss = new WebSocket.Server({ server });

// const storage = multer.diskStorage({
//   destination: function (req, file, cb) {
//     cb(null, "uploads/");
//   },
//   filename: function (req, file, cb) {
//     cb(null, file.originalname); // Preserve the original filename
//   },
// });

// const upload = multer({ storage: storage });

// app.use(express.json());

// app.post("/run-python", upload.single("pdfFile"), (req, res) => {
//   const { vector_store_name } = req.body;
//   const pdfFilePath = req.file.path;

//   // Clear the output directory
//   const outputDir = "output/";
//   fs.readdir(outputDir, (err, files) => {
//     if (err) throw err;
//     for (const file of files) {
//       fs.unlink(path.join(outputDir, file), (err) => {
//         if (err) throw err;
//       });
//     }
//   });

//   const params = {
//     vector_store_name: vector_store_name,
//     pdf_file_path: pdfFilePath,
//   };

//   const pythonProcess = spawn("python3", ["script.py"], {
//     stdio: ["pipe", "pipe", "pipe"],
//   });

//   pythonProcess.stdin.write(JSON.stringify(params));
//   pythonProcess.stdin.end();

//   let result = "";
//   pythonProcess.stdout.on("data", (data) => {
//     result += data.toString();
//   });

//   pythonProcess.stderr.on("data", (data) => {
//     console.error(`stderr: ${data}`);
//   });

//   pythonProcess.on("close", (code) => {
//     // Delete the uploaded file after processing
//     fs.unlinkSync(pdfFilePath);

//     // Send the Excel files as attachments in the response
//     const outputFiles = fs.readdirSync(outputDir);

//     const zipFileName = `${vector_store_name}.zip`;
//     const zipStream = fs.createWriteStream(zipFileName);
//     const archive = archiver("zip", {
//       zlib: { level: 9 }, // Set compression level to maximum
//     });

//     zipStream.on("close", () => {
//       res.set("Content-Type", "application/zip");
//       res.set("Content-Disposition", `attachment; filename=${zipFileName}`);
//       fs.createReadStream(zipFileName).pipe(res);
//     });

//     archive.pipe(zipStream);
//     outputFiles.forEach((file) => {
//       archive.file(path.join(outputDir, file), { name: file });
//     });
//     archive.finalize();
//   });
// });

// // WebSocket connection for real-time updates
// wss.on("connection", (ws) => {
//   const interval = setInterval(() => {
//     ws.send(`Processing... ${new Date().toLocaleTimeString()}`);
//   }, 1000);

//   ws.on("close", () => {
//     clearInterval(interval);
//   });
// });

// app.listen(port, () => {
//   console.log(`Server is running on http://localhost:${port}`);
// });
