using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Cors;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;
using Syncfusion.Collaboration.Core.Interfaces;
using Syncfusion.Collaboration.Core.Models;
using Syncfusion.Collaboration.Core.Services;
using Syncfusion.Collaboration.Core.Transports;
using Syncfusion.EJ2.Spreadsheet;
using Syncfusion.XlsIO;

namespace EJ2SpreadsheetServer.Controllers
{
    /// <summary>
    /// Provides APIs for Spreadsheet collaborative editing actions and participant selections.
    /// </summary>
    [Route("api/[controller]")]
    [ApiController]
    public class CollaborativeEditingController : ControllerBase
    {
        private static readonly ConcurrentDictionary<
            string,
            ConcurrentDictionary<string, SpreadsheetSelectionInfo>>
            RoomSelections = new ConcurrentDictionary<
                string,
                ConcurrentDictionary<string, SpreadsheetSelectionInfo>>();

        private readonly IWebHostEnvironment hostingEnvironment;
        private readonly IActionService actionService;
        private readonly ICollaborationAdapter adapter;
        private readonly IActiveTransport transport;

        private static readonly JsonSerializerSettings ControllerJsonSettings =
            new JsonSerializerSettings
            {
                NullValueHandling = NullValueHandling.Ignore,
                ContractResolver = new DefaultContractResolver
                {
                    NamingStrategy = new CamelCaseNamingStrategy()
                }
            };

        /// <summary>
        /// Initializes a new instance of the <see cref="CollaborativeEditingController"/> class.
        /// </summary>
        /// <param name="hostingEnvironment">Provides access to the server hosting environment.</param>
        /// <param name="actionService">Manages collaborative editing actions and versions.</param>
        /// <param name="adapter">Maps Spreadsheet actions to and from collaboration actions.</param>
        /// <param name="transport">Broadcasts collaboration updates to connected participants.</param>
        public CollaborativeEditingController(
            IWebHostEnvironment hostingEnvironment,
            IActionService actionService,
            ICollaborationAdapter adapter,
            IActiveTransport transport)
        {
            this.hostingEnvironment = hostingEnvironment;
            this.actionService = actionService;
            this.adapter = adapter;
            this.transport = transport;
        }

        /// <summary>
        /// Loads the source workbook, applies pending room actions, and returns the synchronized workbook.
        /// </summary>
        /// <param name="param">Contains the workbook name and collaboration room name.</param>
        /// <returns>The serialized workbook content and current collaboration version.</returns>
        [HttpPost]
        [Route("ImportFile")]
        [EnableCors("AllowAllOrigins")]
        public async Task<string> ImportFile([FromBody] FileInfo param)
        {
            if (param == null || string.IsNullOrWhiteSpace(param.roomName))
            {
                return null;
            }

            string filePath = Path.Combine(
                hostingEnvironment.WebRootPath,
                "Files",
                "Sample.xlsx"
            );

            if (!System.IO.File.Exists(filePath))
            {
                return null;
            }

            try
            {
                List<CollaborationAction> collaborationActions =
                    await actionService.GetPendingOperationsAsync(
                        param.roomName,
                        0,
                        -1
                    );
                List<ActionInfo> spreadsheetActions = collaborationActions == null
                    ? new List<ActionInfo>()
                    : collaborationActions
                        .Select(action =>
                            adapter.MapGenericToControlAction(action) as ActionInfo
                        )
                        .Where(action => action != null)
                        .OrderBy(action => action.Version)
                        .ToList();

                using (ExcelEngine temporaryExcelEngine = new ExcelEngine())
                {
                    IApplication application = temporaryExcelEngine.Excel;
                    IWorkbook temporaryWorkbook = application.Workbooks.Open(filePath);

                    try
                    {
                        if (spreadsheetActions.Count > 0)
                        {
                            CollaborativeEditingHandler handler =
                                new CollaborativeEditingHandler(temporaryWorkbook);

                            foreach (ActionInfo action in spreadsheetActions)
                            {
                                handler.UpdateAction(action);
                            }
                        }

                        using (MemoryStream workbookStream = new MemoryStream())
                        {
                            temporaryWorkbook.SaveAs(workbookStream);
                            workbookStream.Position = 0;

                            string clientFileName = string.IsNullOrWhiteSpace(param.fileName)
                                ? "Sample"
                                : param.fileName;
                            IFormFile formFile = new FormFile(
                                workbookStream,
                                0,
                                workbookStream.Length,
                                clientFileName,
                                "Sample.xlsx"
                            );
                            OpenRequest openRequest = new OpenRequest
                            {
                                File = formFile
                            };
                            string workbookJson = Workbook.Open(openRequest);
                            int currentVersion = spreadsheetActions.Count > 0
                                ? spreadsheetActions.Max(action => action.Version)
                                : 0;
                            DocumentContent content = new DocumentContent
                            {
                                sfdt = workbookJson,
                                version = currentVersion
                            };

                            return JsonConvert.SerializeObject(content);
                        }
                    }
                    finally
                    {
                        temporaryWorkbook.Close();
                    }
                }
            }
            catch (Exception exception)
            {
                Console.WriteLine("Spreadsheet import failed: " + exception);
                return null;
            }
        }

        /// <summary>
        /// Stores a Spreadsheet action and broadcasts the processed action to the collaboration room.
        /// </summary>
        /// <param name="param">Contains the Spreadsheet action and collaboration room information.</param>
        /// <returns>The serialized action after collaboration processing.</returns>
        [HttpPost]
        [Route("UpdateAction")]
        [EnableCors("AllowAllOrigins")]
        public async Task<string> UpdateAction([FromBody] ActionInfo param)
        {
            if (param == null || string.IsNullOrWhiteSpace(param.RoomName))
            {
                return null;
            }

            CollaborationAction collaborationAction =
                adapter.MapControlToGenericAction(param);
            CollaborationAction modifiedAction =
                await actionService.AddOperationAsync(collaborationAction, adapter);
            ActionInfo updatedAction = modifiedAction == null
                ? null
                : adapter.MapGenericToControlAction(modifiedAction) as ActionInfo;

            if (updatedAction == null)
            {
                return null;
            }

            string payload = JsonConvert.SerializeObject(
                updatedAction,
                ControllerJsonSettings
            );
            await transport.SendToGroupAsync(
                param.RoomName,
                "action",
                payload
            );

            return payload;
        }

        /// <summary>
        /// Updates a participant selection and broadcasts it to other users in the room.
        /// </summary>
        /// <param name="param">Contains the participant selection and connection details.</param>
        /// <returns>The updated participant selection.</returns>
        [HttpPost]
        [Route("UpdateSelection")]
        [EnableCors("AllowAllOrigins")]
        public async Task<SpreadsheetSelectionInfo> UpdateSelection(
            [FromBody] SpreadsheetSelectionInfo param)
        {
            if (param == null ||
                string.IsNullOrWhiteSpace(param.RoomName) ||
                string.IsNullOrWhiteSpace(param.ConnectionId))
            {
                return param;
            }

            ConcurrentDictionary<string, SpreadsheetSelectionInfo> selections =
                RoomSelections.GetOrAdd(
                    param.RoomName,
                    _ => new ConcurrentDictionary<string, SpreadsheetSelectionInfo>()
                );
            selections.AddOrUpdate(
                param.ConnectionId,
                param,
                (_, _) => param
            );
            await transport.SendToGroupExceptAsync(
                param.RoomName,
                param.ConnectionId,
                "action",
                param
            );

            return param;
        }

        /// <summary>
        /// Returns the active participant selections for a collaboration room.
        /// </summary>
        /// <param name="roomName">The collaboration room name.</param>
        /// <returns>The active participant selections in the room.</returns>
        [HttpGet]
        [Route("GetRoomSelections/{roomName}")]
        [EnableCors("AllowAllOrigins")]
        public ActionResult<List<SpreadsheetSelectionInfo>> GetRoomSelections(
            string roomName)
        {
            if (string.IsNullOrWhiteSpace(roomName) ||
                !RoomSelections.TryGetValue(
                    roomName,
                    out ConcurrentDictionary<string, SpreadsheetSelectionInfo> selections
                ))
            {
                return Ok(new List<SpreadsheetSelectionInfo>());
            }

            return Ok(selections.Values.ToList());
        }

        /// <summary>
        /// Removes a disconnected participant selection from the collaboration room.
        /// </summary>
        /// <param name="request">Contains the collaboration room and connection identifiers.</param>
        /// <returns>An HTTP success result.</returns>
        [HttpPost]
        [Route("RemoveUserSelection")]
        [EnableCors("AllowAllOrigins")]
        public ActionResult RemoveUserSelection(
            [FromBody] RemoveSelectionRequest request)
        {
            if (request == null ||
                string.IsNullOrWhiteSpace(request.RoomName) ||
                string.IsNullOrWhiteSpace(request.ConnectionId))
            {
                return Ok();
            }

            if (RoomSelections.TryGetValue(
                request.RoomName,
                out ConcurrentDictionary<string, SpreadsheetSelectionInfo> selections
            ))
            {
                selections.TryRemove(request.ConnectionId, out _);

                if (selections.IsEmpty)
                {
                    RoomSelections.TryRemove(request.RoomName, out _);
                }
            }

            return Ok();
        }

        /// <summary>
        /// Returns collaboration actions newer than the client's last synchronized version.
        /// </summary>
        /// <param name="param">Contains the room name and last synchronized version.</param>
        /// <returns>The serialized list of pending Spreadsheet actions.</returns>
        [HttpPost]
        [Route("GetActionsFromServer")]
        [EnableCors("AllowAllOrigins")]
        public async Task<ActionResult<List<ActionInfo>>> GetActionsFromServer(
            [FromBody] ActionInfo param)
        {
            if (param == null || string.IsNullOrWhiteSpace(param.RoomName))
            {
                return Ok(new List<ActionInfo>());
            }

            int lastSyncedVersion = param.Version;
            List<CollaborationAction> collaborationActions =
                await actionService.GetEffectivePendingVersionAsync(
                    param.RoomName,
                    lastSyncedVersion
                );
            List<ActionInfo> actions = collaborationActions == null
                ? new List<ActionInfo>()
                : collaborationActions
                    .Select(action =>
                        adapter.MapGenericToControlAction(action) as ActionInfo
                    )
                    .Where(action =>
                        action != null && action.Version > lastSyncedVersion
                    )
                    .OrderBy(action => action.Version)
                    .ToList();
            string payload = JsonConvert.SerializeObject(
                actions,
                ControllerJsonSettings
            );

            return Ok(payload);
        }

        /// <summary>
        /// Represents a request to remove a participant selection.
        /// </summary>
        public class RemoveSelectionRequest
        {
            /// <summary>
            /// Gets or sets the collaboration room name.
            /// </summary>
            public string RoomName { get; set; }

            /// <summary>
            /// Gets or sets the participant connection identifier.
            /// </summary>
            public string ConnectionId { get; set; }
        }

        /// <summary>
        /// Represents the synchronized workbook content and collaboration version.
        /// </summary>
        public class DocumentContent
        {
            /// <summary>
            /// Gets or sets the current collaboration version.
            /// </summary>
            public int version { get; set; }

            /// <summary>
            /// Gets or sets the serialized workbook content.
            /// </summary>
            public string sfdt { get; set; }
        }

        /// <summary>
        /// Represents a workbook import request.
        /// </summary>
        public class FileInfo
        {
            /// <summary>
            /// Gets or sets the workbook file name.
            /// </summary>
            public string fileName { get; set; }

            /// <summary>
            /// Gets or sets the collaboration room name.
            /// </summary>
            public string roomName { get; set; }
        }
    }
}
