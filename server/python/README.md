# Mail merge with Vue DOCX Editor and Spreadsheet

## Overview

This sample demonstrates a web-based solution that streamlines the creation of commercial real estate (CRE) appraisal reports through a combination of document editing, spreadsheet-based data management, mail merge, and AI-assisted content generation.

The solution enables users to:

- Create and edit appraisal report templates
- Manage property and tenant data using an integrated spreadsheet
- Generate appraisal reports through mail merge
- Preview merged reports before publishing
- Export reports to DOCX or PDF
- Use AI assistance for drafting, refining, summarizing, and improving report content

---

## Solution Components

### DOCX Editor

A Microsoft Word-like document editing experience powered by the Syncfusion Document Editor.

#### Key Capabilities

- Create and edit appraisal report templates
- Insert and manage mail merge fields
- Save template changes
- Download reports as DOCX
- Export reports as PDF
- Preview merged reports with live property data

---

### Spreadsheet Editor

An integrated spreadsheet experience used for managing report data.

#### Key Capabilities

- Edit property information
- Maintain tenant rent roll information
- Update appraisal summary metrics
- Save updates directly to the shared data source
- Support formulas and calculated values

---

### Mail Merge Engine

Generate business documents by combining document templates with structured spreadsheet data.

#### Key Capabilities

- Support for single-record and multi-record data sources
- Dynamic field mapping between spreadsheets and templates
- Group mail merge for repeating sections and tabular data
- Live preview of merged documents
- Support for complex reports containing summaries and detailed schedules
- Export merged documents to DOCX and PDF

> **Note**
>
> After Mail Merge is executed, the generated document contains actual values rather than mail merge fields. To generate another report using updated spreadsheet data, use the **Load Word Template** option to reload the original template before executing Mail Merge again.

---

### AI Assist

Integrated AI assistance helps users draft and improve appraisal reports.

#### Available Actions

- Improve grammar and readability
- Summarize content

#### User Experience

Users can:

- Select content and request improvements
- Generate new content from natural language prompts
- Insert generated content into the document
- Replace existing content with AI-generated recommendations

---

# Running the Sample

## Server-Side Setup (Python Web Service)

### Navigate to the .NET Wrapper Project

```bash
cd NETStandardWrapperLibrary
```

### Build and Publish the NETStandardWrapperLibrary

```bash
dotnet build -c Release
dotnet publish -c Release
```

### Navigate to the Root folder

```bash
cd ../mail-merge-with-vue-docx-editor-and-spreadsheet
```

### Install Dependencies

```bash
pip install -r requirements.txt
```
### Configure Settings

Edit `appsettings.json` at the repo root (or set matching env vars):

```json
{
  "Syncfusion":  { "LicenseKey": "<your-syncfusion-key>" },
  "AzureOpenAI": {
    "Endpoint":      "https://<resource>.openai.azure.com/",
    "ApiKey":        "<your-azure-openai-key>",
    "DeploymentName": "gpt-4o",
    "ApiVersion":    "2024-02-15-preview"
  },
  "Server":      { "Host": "0.0.0.0", "Port": 5000, "FilesRoot": "Files" }
}
```

### Start the Python Service

```bash
python app.py

or

py app.py
```

---

## Client-Side Setup

### Navigate to the Vue Application

```bash
cd frontend
```

### Install Dependencies

```bash
npm install
```

### Configure Service URLs

All URLs live in `src/data/sampleTemplates.js` and resolve to
`http://localhost:5000` by default.

**Document Editor**

```javascript
export const DOCUMENT_EDITOR_SERVICE_URL =
  `${DOCUMENT_EDITOR_BASE_URL}/api/DocumentEditor/`;
```

**Spreadsheet** (in `src/components/SpreadsheetComponent.vue`)

```javascript
openUrl:  "Open",
saveUrl:  "Save",
// Shared Excel: GET  /OpenRentRoll
//               POST /SaveRentRoll
```

**AI Process** (in `src/ai/ai-models.js`)

```javascript
const AI_API_BASE = 'api/DocumentEditor';
//   POST /Process
```

### Run the Application

```bash
npm run dev
```

Open the application using the URL displayed in the terminal
(usually `http://localhost:5173/`).

---

## Business Workflow

### Step 1: Open the Report Template

Open the Property Appraisal Report Template in the DOCX Editor.

### Step 2: Review and Update Data

Open the Property Portfolio Data workbook in the Spreadsheet Editor and update:

- Property information
- Tenant rent roll data
- Appraisal summary data

### Step 3: Generate the Report

Execute the mail merge process to combine the report template with the Excel data source.

### Step 4: Review the Output

Preview the generated report and validate:

- Property appraisal summary
- Financial metrics
- Rent roll information

### Step 5: Enhance with AI

Use AI Assist to improve narratives, summaries, and supporting commentary.

### Step 6: Publish

Export the completed report as:

- DOCX
- PDF

---

## Key Benefits

### Improved Productivity

Eliminates manual data entry and significantly reduces report preparation time.

### Reduced Errors

Ensures reports are generated from a centralized and consistent data source.

### Faster Report Generation

Automatically produces appraisal reports using the latest spreadsheet data.

### AI-Assisted Authoring

Accelerates creation of summaries, narratives, and descriptive report sections.

### Familiar User Experience

Provides Word-like and Excel-like editing experiences directly within the browser.

---

# License 

This is a commercial product and requires a paid license for possession or use. Syncfusion's licensed software, including this component, is subject to the terms and conditions of [Syncfusion's EULA](https://www.syncfusion.com/license/studio/22.2.5/syncfusion_essential_studio_eula.pdf?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples). You can purchase a license [here](https://www.syncfusion.com/sales/products?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples) or start a free 30\-day trial [here](https://www.syncfusion.com/account/manage-trials/start-trials?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples).

# About Syncfusion&reg;

Founded in 2001 and headquartered in Research Triangle Park, N.C., Syncfusion&reg; has more than 29,000 customers and more than 1 million users, including large financial institutions, Fortune 500 companies, and global IT consultancies.

Today, we provide 1700+ components and frameworks for web ([Blazor](https://www.syncfusion.com/blazor-components?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [ASP.NET Core](https://www.syncfusion.com/aspnet-core-ui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [ASP.NET MVC](https://www.syncfusion.com/aspnet-mvc-ui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [ASP.NET WebForms](https://www.syncfusion.com/jquery/aspnet-webforms-ui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [JavaScript](https://www.syncfusion.com/javascript-ui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [Angular](https://www.syncfusion.com/angular-ui-components?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [React](https://www.syncfusion.com/react-ui-components?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [Vue](https://www.syncfusion.com/vue-ui-components?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), and [Flutter](https://www.syncfusion.com/flutter-widgets?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples)), mobile ([Xamarin](https://www.syncfusion.com/xamarin-ui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [Flutter](https://www.syncfusion.com/flutter-widgets?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [UWP](https://www.syncfusion.com/uwp-ui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), and [JavaScript](https://www.syncfusion.com/javascript-ui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [.NET MAUI](https://www.syncfusion.com/maui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples)) and desktop development ([WinForms](https://www.syncfusion.com/winforms-ui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [WPF](https://www.syncfusion.com/wpf-ui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [WinUI](https://www.syncfusion.com/winui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [Flutter](https://www.syncfusion.com/flutter-widgets?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), [UWP](https://www.syncfusion.com/uwp-ui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples), and [.NET MAUI](https://www.syncfusion.com/maui-controls?utm_source=github&utm_medium=listing&utm_campaign=github-react-docx-editor-examples)) a. We provide ready-to-deploy enterprise software for dashboards, reports, data integration, and big data processing. Many customers have saved millions in licensing fees by deploying our software.