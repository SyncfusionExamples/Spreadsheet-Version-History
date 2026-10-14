using Syncfusion.EJ2.Spreadsheet;
using Syncfusion.XlsIO;
using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json;

namespace WebServiceLibrary
{
    public class SpreadsheetEditor
    {
        public string Open(byte[] byteArr)
        {
            // Loading the bytes array to stream.
            MemoryStream stream = new MemoryStream(byteArr);
            //Creates a new instance for ExcelEngine
            ExcelEngine excelEngine = new ExcelEngine();

            //Initialize IApplication
            IApplication application = excelEngine.Excel;
            //Loads or open an existing workbook through Open method of IWorkbooks
            IWorkbook workbook = application.Workbooks.Open(stream);
            //OpenRequest open = new OpenRequest();
            //// Converting the stream into FormFile.
            //open.File = new FormFile(stream, 0, bytes.Length, "Sample", "Sample." + "xlsx");
            //var result = Workbook.Open(open);
            var spreadsheet = new SheetOpen();
            var result = spreadsheet.ProcessWorkBook(workbook, new OpenRequest());
            return result;
        }

        public string OpenWithActions(byte[] byteArr, string actionsJson)
        {
            MemoryStream stream = new MemoryStream(byteArr);
            ExcelEngine excelEngine = new ExcelEngine();
            IApplication application = excelEngine.Excel;
            IWorkbook workbook = application.Workbooks.Open(stream);
            List<ActionInfo> actions = new List<ActionInfo>();
            try
            {
                if (!string.IsNullOrWhiteSpace(actionsJson))
                {
                    actions = JsonConvert.DeserializeObject<List<ActionInfo>>(
                        actionsJson
                    ) ?? new List<ActionInfo>();

                    if (actions.Count > 0)
                    {
                        actions = actions
                            .OrderBy(x => x.Version)
                            .ToList();

                        CollaborativeEditingHandler handler =
                            new CollaborativeEditingHandler(workbook);

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

    public class CollaborativeOpenResult
    {
        [JsonProperty("sfdt")]
        public string Sfdt { get; set; }

        [JsonProperty("version")]
        public int Version { get; set; }
    }

}
 