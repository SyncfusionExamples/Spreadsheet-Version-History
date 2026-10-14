using Syncfusion.EJ2.Spreadsheet;
using Syncfusion.XlsIO;
using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace WebServiceLibrary
{
    /// <summary>
    /// Wrapper for Spreadsheet collaborative editing.
    /// 
    /// Provides methods to apply actions to workbooks and transform
    /// concurrent actions using Syncfusion CollaborativeEditingHandler.
    /// </summary>
    public class SpreadsheetCollaborationWrapper
    {
        /// <summary>
        /// Applies actions to a workbook and returns Spreadsheet workbook JSON.
        /// 
        /// Deserializes actions from JSON, sorts by Version, applies each via
        /// CollaborativeEditingHandler.UpdateAction, and converts the result
        /// to Spreadsheet workbook JSON format.
        /// 
        /// Parameters:
        /// - workbookData: XLSX workbook as byte array
        /// - actionsJson: JSON array of ActionInfo objects, or null/empty/"[]" for no actions
        /// 
        /// Returns:
        /// - Spreadsheet workbook JSON string
        /// 
        /// Throws:
        /// - ArgumentNullException if workbookData is null or empty
        /// - InvalidOperationException if processing fails
        /// </summary>
        public string ImportFile(byte[] workbookData, string actionsJson)
        {
            if (workbookData == null || workbookData.Length == 0)
            {
                throw new ArgumentNullException(nameof(workbookData), "Workbook data cannot be null or empty");
            }

            // Treat null, empty, whitespace, or "[]" as no actions
            if (string.IsNullOrWhiteSpace(actionsJson) || actionsJson.Trim() == "[]")
            {
                return OpenWorkbookToJson(workbookData);
            }

            try
            {
                // Deserialize actions into List<ActionInfo>
                List<ActionInfo> actions = JsonConvert.DeserializeObject<List<ActionInfo>>(actionsJson);

                if (actions == null || actions.Count == 0)
                {
                    return OpenWorkbookToJson(workbookData);
                }

                // Sort by Version
                actions = actions.OrderBy(a => a?.Version ?? 0).ToList();

                // Apply non-null actions
                byte[] modifiedBytes = ApplyActionsToWorkbook(workbookData, actions);

                // Convert to Spreadsheet workbook JSON
                return OpenWorkbookToJson(modifiedBytes);
            }
            catch (JsonException ex)
            {
                throw new InvalidOperationException(
                    $"Failed to deserialize actions JSON: {ex.Message}", ex);
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException(
                    $"Failed to process ImportFile: {ex.Message}", ex);
            }
        }

        /// <summary>
        /// Transforms a list of concurrent actions using Syncfusion's
        /// CollaborativeEditingHandler.TransformOperations.
        /// 
        /// Deserializes actionsJson into List&lt;ActionInfo&gt;, calls
        /// CollaborativeEditingHandler.TransformOperations, and serializes
        /// the result back to JSON.
        /// 
        /// Parameters:
        /// - actionsJson: JSON array of ActionInfo objects to transform
        /// 
        /// Returns:
        /// - JSON array of transformed ActionInfo objects, or "[]" if empty
        /// 
        /// Throws:
        /// - ArgumentNullException if actionsJson is null or empty
        /// - InvalidOperationException if processing fails
        /// </summary>
        public string TransformOperations(string actionsJson)
        {
            if (string.IsNullOrWhiteSpace(actionsJson))
            {
                throw new ArgumentNullException(nameof(actionsJson), "Actions JSON cannot be null or empty");
            }

            try
            {
                // Deserialize into List<ActionInfo>
                List<ActionInfo> actions = JsonConvert.DeserializeObject<List<ActionInfo>>(actionsJson);

                if (actions == null || actions.Count == 0)
                {
                    return "[]";
                }

                // Invoke CollaborativeEditingHandler.TransformOperations
                CollaborativeEditingHandler.TransformOperations(actions);

                // Serialize and return
                return JsonConvert.SerializeObject(actions);
            }
            catch (JsonException ex)
            {
                throw new InvalidOperationException(
                    $"Failed to deserialize actions JSON: {ex.Message}", ex);
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException(
                    $"Failed to transform operations: {ex.Message}", ex);
            }
        }

        // ====================================================================
        // Private Helpers
        // ====================================================================

        private string OpenWorkbookToJson(byte[] workbookData)
        {
            if (workbookData == null || workbookData.Length == 0)
            {
                throw new ArgumentException("Workbook data cannot be null or empty");
            }

            var editor = new SpreadsheetEditor();
            return editor.Open(workbookData);
        }

        private byte[] ApplyActionsToWorkbook(byte[] workbookData, List<ActionInfo> actions)
        {
            if (workbookData == null || workbookData.Length == 0)
            {
                throw new ArgumentException("Workbook data cannot be null or empty");
            }

            if (actions == null || actions.Count == 0)
            {
                return workbookData;
            }

            ExcelEngine excelEngine = null;
            IWorkbook workbook = null;

            try
            {
                using (var stream = new MemoryStream(workbookData))
                {
                    excelEngine = new ExcelEngine();
                    IApplication application = excelEngine.Excel;
                    workbook = application.Workbooks.Open(stream);
                }

                var handler = new CollaborativeEditingHandler(workbook);

                foreach (var action in actions)
                {
                    if (action != null)
                    {
                        handler.UpdateAction(action);
                    }
                }

                return SaveWorkbookToBytes(workbook);
            }
            finally
            {
                workbook?.Close();
                excelEngine?.Dispose();
            }
        }

        private byte[] SaveWorkbookToBytes(IWorkbook workbook)
        {
            if (workbook == null)
            {
                throw new ArgumentNullException(nameof(workbook));
            }

            using (var stream = new MemoryStream())
            {
                workbook.SaveAs(stream);
                return stream.ToArray();
            }
        }
    }
}
