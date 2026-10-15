using Newtonsoft.Json;
using Syncfusion.EJ2.Spreadsheet;
using Syncfusion.XlsIO;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace WebServiceLibrary
{
    public class SpreadsheetEditor
    {
        public string Open(byte[] byteArr)
        {
            MemoryStream stream = new MemoryStream(byteArr);
            ExcelEngine excelEngine = new ExcelEngine();
            IApplication application = excelEngine.Excel;
            IWorkbook workbook = application.Workbooks.Open(stream);
            var spreadsheet = new SheetOpen();
            var result = spreadsheet.ProcessWorkBook(
                workbook,
                new OpenRequest()
            );
            return result;
        }

        public string OpenWithActions(
            byte[] byteArr,
            string actionsJson
        )
        {
            MemoryStream stream = new MemoryStream(byteArr);
            ExcelEngine excelEngine = new ExcelEngine();
            IApplication application = excelEngine.Excel;
            IWorkbook workbook = application.Workbooks.Open(stream);
            List<ActionInfo> actions = new List<ActionInfo>();

            try
            {
                if (!string.IsNullOrWhiteSpace(actionsJson)
                    && actionsJson.Trim() != "[]")
                {
                    actions = JsonConvert
                        .DeserializeObject<List<ActionInfo>>(
                            actionsJson
                        ) ?? new List<ActionInfo>();

                    actions = actions
                        .Where(a => a != null)
                        .ToList();

                    if (actions.Count > 0)
                    {
                        actions = actions
                            .OrderBy(x => x.Version)
                            .ToList();

                        CollaborativeEditingHandler handler =
                            new CollaborativeEditingHandler(
                                workbook
                            );

                        foreach (ActionInfo action in actions)
                        {
                            handler.UpdateAction(action);
                        }
                    }
                }

                var spreadsheet = new SheetOpen();
                int currentVersion =
                    actions.Count > 0
                        ? actions.Max(x => x.Version)
                        : 0;

                CollaborativeOpenResult result =
                    new CollaborativeOpenResult
                    {
                        Sfdt = spreadsheet.ProcessWorkBook(
                            workbook,
                            new OpenRequest()
                        ),
                        Version = currentVersion
                    };

                return JsonConvert.SerializeObject(result);
            }
            finally
            {
                workbook.Close();
                excelEngine.Dispose();
            }
        }

        public Stream Save(SaveSettings settings)
        {
            return Workbook.Save<Stream>(settings);
        }
    }

    public class SpreadsheetCollaborationWrapper
    {
        public string ImportFile(
            byte[] workbookData,
            string actionsJson
        )
        {
            if (workbookData == null
                || workbookData.Length == 0)
            {
                throw new ArgumentNullException(
                    nameof(workbookData),
                    "Workbook data cannot be null or empty"
                );
            }

            if (string.IsNullOrWhiteSpace(actionsJson)
                || actionsJson.Trim() == "[]")
            {
                return OpenWorkbookToJson(workbookData);
            }

            try
            {
                List<ActionInfo> actions =
                    JsonConvert.DeserializeObject<
                        List<ActionInfo>
                    >(actionsJson);

                if (actions == null
                    || actions.Count == 0)
                {
                    return OpenWorkbookToJson(
                        workbookData
                    );
                }

                actions = actions
                    .Where(a => a != null)
                    .OrderBy(a => a.Version)
                    .ToList();

                byte[] modifiedBytes =
                    ApplyActionsToWorkbook(
                        workbookData,
                        actions
                    );

                return OpenWorkbookToJson(
                    modifiedBytes
                );
            }
            catch (JsonException ex)
            {
                throw new InvalidOperationException(
                    $"Failed to deserialize actions JSON: "
                    + $"{ex.Message}",
                    ex
                );
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException(
                    $"Failed to process ImportFile: "
                    + $"{ex.Message}",
                    ex
                );
            }
        }

        public string TransformOperations(
            string actionsJson
        )
        {
            if (string.IsNullOrWhiteSpace(actionsJson))
            {
                throw new ArgumentNullException(
                    nameof(actionsJson),
                    "Actions JSON cannot be null or empty"
                );
            }

            try
            {
                List<ActionInfo> actions =
                    JsonConvert.DeserializeObject<
                        List<ActionInfo>
                    >(actionsJson);

                if (actions == null
                    || actions.Count == 0)
                {
                    return "[]";
                }

                CollaborativeEditingHandler
                    .TransformOperations(actions);

                return JsonConvert.SerializeObject(
                    actions
                );
            }
            catch (JsonException ex)
            {
                throw new InvalidOperationException(
                    $"Failed to deserialize actions JSON: "
                    + $"{ex.Message}",
                    ex
                );
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException(
                    $"Failed to transform operations: "
                    + $"{ex.Message}",
                    ex
                );
            }
        }

        public byte[] ApplyCollaborativeActions(
            byte[] workbookBytes,
            string actionsJson
        )
        {
            if (workbookBytes == null
                || workbookBytes.Length == 0)
            {
                throw new ArgumentNullException(
                    nameof(workbookBytes),
                    "Workbook bytes cannot be null or empty"
                );
            }

            if (string.IsNullOrWhiteSpace(actionsJson)
                || actionsJson.Trim() == "[]")
            {
                return workbookBytes;
            }

            try
            {
                List<ActionInfo> actions =
                    JsonConvert.DeserializeObject<
                        List<ActionInfo>
                    >(actionsJson);

                if (actions == null
                    || actions.Count == 0)
                {
                    return workbookBytes;
                }

                actions = actions
                    .Where(a => a != null)
                    .ToList();

                if (actions.Count == 0)
                {
                    return workbookBytes;
                }

                actions = actions
                    .OrderBy(a => a.Version)
                    .ToList();

                return ApplyActionsToWorkbook(
                    workbookBytes,
                    actions
                );
            }
            catch (JsonException ex)
            {
                throw new InvalidOperationException(
                    $"Failed to deserialize actions JSON: "
                    + $"{ex.Message}",
                    ex
                );
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException(
                    $"Failed to apply collaborative actions: "
                    + $"{ex.Message}",
                    ex
                );
            }
        }

        private string OpenWorkbookToJson(
            byte[] workbookData
        )
        {
            if (workbookData == null
                || workbookData.Length == 0)
            {
                throw new ArgumentException(
                    "Workbook data cannot be null or empty"
                );
            }

            var editor = new SpreadsheetEditor();
            return editor.Open(workbookData);
        }

        private byte[] ApplyActionsToWorkbook(
            byte[] workbookData,
            List<ActionInfo> actions
        )
        {
            if (workbookData == null
                || workbookData.Length == 0)
            {
                throw new ArgumentException(
                    "Workbook data cannot be null or empty"
                );
            }

            if (actions == null
                || actions.Count == 0)
            {
                return workbookData;
            }

            ExcelEngine excelEngine = null;
            IWorkbook workbook = null;

            try
            {
                using (var stream =
                    new MemoryStream(workbookData))
                {
                    excelEngine = new ExcelEngine();
                    IApplication application =
                        excelEngine.Excel;
                    workbook = application.Workbooks
                        .Open(stream);
                }

                var handler =
                    new CollaborativeEditingHandler(
                        workbook
                    );

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

        private byte[] SaveWorkbookToBytes(
            IWorkbook workbook
        )
        {
            if (workbook == null)
            {
                throw new ArgumentNullException(
                    nameof(workbook)
                );
            }

            using (var stream = new MemoryStream())
            {
                workbook.SaveAs(stream);
                return stream.ToArray();
            }
        }
    }

    public class CollaborativeOpenResult
    {
        [JsonProperty("sfdt")]
        public string Sfdt { get; set; }

        [JsonProperty("version")]
        public int Version { get; set; }
    }
}
 