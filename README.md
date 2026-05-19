# Ollama Manager by OreX

**Ollama Manager by OreX** is a user-friendly graphical utility for converting and managing local LLM models within the Ollama ecosystem.

This tool allows you to easily convert GGUF files to Ollama models, configure inference parameters (Modelfile), and manage installed models through an intuitive interface.

## 🚀 Key Features

* **GGUF Conversion:** Convenient import of GGUF files, automatic path detection, and Modelfile generation.
  ![Converter GGUF](http://orex)
* **Ollama Management:** View a list of installed models, read metadata, and delete models.
  ![Manager Ollama](http://orex)
* **Flexible Parameters:** Configure `Temperature`, `Top-K`, `Top-P`, `Repeat Penalty`, and context size (`num_ctx`) with visual activity control (checkboxes).
* **System Prompt:** Edit and save system prompts for each model.
* **Chat Template (Jinja → Go):** Built-in chat template converter from LM Studio format (Jinja) to Ollama format (Go).
* **Model Store:** Built-in browser for searching and downloading models directly from [ollama.com](https://ollama.com).
  ![Ollama Store](http://orex)
* **Multilingual and Themes:** Support for 7 interface languages and 4 visual themes (including "Hacker").

## 🛠 Installation and Launch

### Requirements

* Installed [Ollama](https://ollama.com/).
* Python 3.x.
* For built-in browser support: `pip install PySide6[webengine]`.

### Launch from Source Code

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Launch the application via `start.bat` (Windows) or:

```bash
python app.py
```

## 📦 Building a Portable Version

To create a single `.exe` file:

1. Install `pyinstaller`: `pip install pyinstaller`
2. Run the build script (`build.bat` or the `pyinstaller` command).
3. The application will automatically use `settings.json` and `locales.json` from the folder with the `.exe`.

## 🎨 Screenshots

*(You can add your interface screenshots here)*

## 🛠 Technology Stack

* **Language:** Python
* **GUI:** PySide6 (Qt)
* **Browser:** QtWebEngine
* **Build:** PyInstaller

## 👤 Author

**OreX** (Oleg Konuykov)

---

### How to use?

1. Drag and drop the GGUF file into the program window.
2. Enter the desired model name.
3. Configure parameters (temperature, prompt, etc.) by toggling the necessary checkboxes.
4. Click **"Create model in Ollama"**.

---

*This project was created to simplify working with local AI models.*
