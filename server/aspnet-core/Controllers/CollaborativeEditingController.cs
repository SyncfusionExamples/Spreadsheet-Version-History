using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using EJ2SpreadsheetServer.Models;
using Microsoft.AspNetCore.Cors;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;
using Newtonsoft.Json.Linq;
using Syncfusion.Collaboration.Core.Interfaces;
using Syncfusion.Collaboration.Core.Models;
using Syncfusion.Collaboration.Core.Services;
using Syncfusion.Collaboration.Core.Transports;
using Syncfusion.EJ2.Spreadsheet;
using Syncfusion.XlsIO;

namespace EJ2SpreadsheetServer.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class CollaborativeEditingController : ControllerBase
    {
        private const string DefaultWorkbookName = "Sample.xlsx";
        private const string CurrentWorkbookName = "Current.xlsx";
        private const string VersionMetadataFileName = "versions.json";

        private static readonly ConcurrentDictionary<
            string,
            ConcurrentDictionary<string, SpreadsheetSelectionInfo>>
            RoomSelections =
                new ConcurrentDictionary<
                    string,
                    ConcurrentDictionary<
                        string,
                        SpreadsheetSelectionInfo>>();

        private static readonly ConcurrentDictionary<string, SemaphoreSlim>
            VersionLocks =
                new ConcurrentDictionary<string, SemaphoreSlim>();

        private static readonly ConcurrentDictionary<string, RestoreRevisionInfo>
            RoomRestoreRevisions =
                new ConcurrentDictionary<string, RestoreRevisionInfo>();

        private static readonly ConcurrentDictionary<string, string>
            RoomActionUsers =
                new ConcurrentDictionary<string, string>();

        private static readonly JsonSerializerSettings
            ControllerJsonSettings = new JsonSerializerSettings
            {
                NullValueHandling = NullValueHandling.Ignore,
                ContractResolver = new DefaultContractResolver
                {
                    NamingStrategy = new CamelCaseNamingStrategy()
                }
            };

        private readonly IWebHostEnvironment hostingEnvironment;
        private readonly IActionService actionService;
        private readonly ICollaborationAdapter adapter;
        private readonly IActiveTransport transport;

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

        [HttpPost]
        [Route("ImportFile")]
        [EnableCors("AllowAllOrigins")]
        public async Task<string> ImportFile(
            [FromBody] FileInfo param)
        {
            if (param == null ||
                string.IsNullOrWhiteSpace(param.roomName))
            {
                return null;
            }

            try
            {
                MaterializedWorkbook materializedWorkbook =
                    await MaterializeRoomWorkbookAsync(
                        param.roomName
                    );

                if (materializedWorkbook == null)
                {
                    return null;
                }

                string clientFileName =
                    string.IsNullOrWhiteSpace(param.fileName)
                        ? "Sample"
                        : param.fileName;

                string workbookJson = ConvertWorkbookToJson(
                    materializedWorkbook.WorkbookData,
                    clientFileName
                );

                DocumentContent content = new DocumentContent
                {
                    sfdt = workbookJson,
                    version = materializedWorkbook.Version
                };

                return JsonConvert.SerializeObject(content);
            }
            catch (Exception exception)
            {
                Console.WriteLine(
                    "Spreadsheet import failed: " +
                    exception
                );
                return null;
            }
        }

        [HttpPost]
        [Route("UpdateAction")]
        [EnableCors("AllowAllOrigins")]
        public async Task<string> UpdateAction(
            [FromBody] JObject request)
        {
            if (request == null)
            {
                return null;
            }

            ActionInfo param = request.ToObject<ActionInfo>();

            if (param == null ||
                string.IsNullOrWhiteSpace(param.RoomName))
            {
                return null;
            }

            RoomActionUsers.TryGetValue(
                param.RoomName,
                out string currentUser
            );

            CollaborationAction collaborationAction =
                adapter.MapControlToGenericAction(param);
            CollaborationAction modifiedAction =
                await actionService.AddOperationAsync(
                    collaborationAction,
                    adapter
                );
            ActionInfo updatedAction =
                modifiedAction == null
                    ? null
                    : adapter.MapGenericToControlAction(
                        modifiedAction
                    ) as ActionInfo;

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

            try
            {
                await CreateAutomaticVersionAsync(
                    param.RoomName,
                    updatedAction,
                    currentUser
                );
            }
            catch (Exception exception)
            {
                Console.WriteLine(
                    "Automatic version creation failed: " +
                    exception
                );
            }

            return payload;
        }

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
                    _ => new ConcurrentDictionary<
                        string,
                        SpreadsheetSelectionInfo>()
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

        [HttpGet]
        [Route("GetRoomSelections/{roomName}")]
        [EnableCors("AllowAllOrigins")]
        public ActionResult<List<SpreadsheetSelectionInfo>>
            GetRoomSelections(string roomName)
        {
            if (string.IsNullOrWhiteSpace(roomName) ||
                !RoomSelections.TryGetValue(
                    roomName,
                    out ConcurrentDictionary<
                        string,
                        SpreadsheetSelectionInfo> selections
                ))
            {
                return Ok(new List<SpreadsheetSelectionInfo>());
            }

            return Ok(selections.Values.ToList());
        }

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
                out ConcurrentDictionary<
                    string,
                    SpreadsheetSelectionInfo> selections
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

        [HttpPost]
        [Route("GetActionsFromServer")]
        [EnableCors("AllowAllOrigins")]
        public async Task<ActionResult<List<ActionInfo>>>
            GetActionsFromServer(
                [FromBody] ActionInfo param)
        {
            if (param == null ||
                string.IsNullOrWhiteSpace(param.RoomName))
            {
                return Ok(new List<ActionInfo>());
            }

            int lastSyncedVersion = param.Version;
            List<CollaborationAction> collaborationActions =
                await actionService.GetEffectivePendingVersionAsync(
                    param.RoomName,
                    lastSyncedVersion
                );
            List<ActionInfo> actions =
                collaborationActions == null
                    ? new List<ActionInfo>()
                    : collaborationActions
                        .Select(action =>
                            adapter.MapGenericToControlAction(
                                action
                            ) as ActionInfo
                        )
                        .Where(action =>
                            action != null &&
                            action.Version > lastSyncedVersion
                        )
                        .OrderBy(action => action.Version)
                        .ToList();
            string payload = JsonConvert.SerializeObject(
                actions,
                ControllerJsonSettings
            );

            return Ok(payload);
        }

        [HttpGet]
        [Route("GetVersionHistory/{roomName}")]
        [EnableCors("AllowAllOrigins")]
        public async Task<IActionResult> GetVersionHistory(
            string roomName)
        {
            if (string.IsNullOrWhiteSpace(roomName))
            {
                return Content(
                    "[]",
                    "application/json",
                    Encoding.UTF8
                );
            }

            SpreadsheetVersionHistory history =
                await ReadVersionHistoryAsync(roomName);
            List<SpreadsheetVersionInfo> versions =
                history.Versions
                    .OrderByDescending(
                        version => version.CreatedAtUtc
                    )
                    .ToList();
            string response = JsonConvert.SerializeObject(
                versions,
                ControllerJsonSettings
            );

            return Content(
                response,
                "application/json",
                Encoding.UTF8
            );
        }

        [HttpPost]
        [Route("GetVersionWorkbook")]
        [EnableCors("AllowAllOrigins")]
        public async Task<IActionResult> GetVersionWorkbook(
            [FromBody] SpreadsheetVersionRequest request)
        {
            if (request == null ||
                string.IsNullOrWhiteSpace(request.RoomName) ||
                string.IsNullOrWhiteSpace(request.VersionId))
            {
                return BadRequest(
                    "Room name and version ID are required."
                );
            }

            string versionPath = GetVersionWorkbookPath(
                request.RoomName,
                request.VersionId
            );

            if (!System.IO.File.Exists(versionPath))
            {
                return NotFound(
                    "The requested version does not exist."
                );
            }

            byte[] workbookData =
                await System.IO.File.ReadAllBytesAsync(versionPath);
            SpreadsheetVersionInfo versionInfo =
                await GetVersionInfoAsync(
                    request.RoomName,
                    request.VersionId
                );
            string workbookJson = ConvertWorkbookToJson(
                workbookData,
                versionInfo?.FileName ?? DefaultWorkbookName
            );
            DocumentContent content = new DocumentContent
            {
                sfdt = workbookJson,
                version = versionInfo?.CollaborationVersion ?? 0
            };
            string response = JsonConvert.SerializeObject(
                content,
                ControllerJsonSettings
            );

            return Content(
                response,
                "application/json",
                Encoding.UTF8
            );
        }

        [HttpPost]
        [Route("RestoreVersion")]
        [EnableCors("AllowAllOrigins")]
        public async Task<ActionResult> RestoreVersion(
            [FromBody] SpreadsheetVersionRequest request)
        {
            if (request == null ||
                string.IsNullOrWhiteSpace(request.RoomName) ||
                string.IsNullOrWhiteSpace(request.VersionId))
            {
                return BadRequest(
                    "Room name and version ID are required."
                );
            }

            string roomName = request.RoomName.Trim();
            string versionPath = GetVersionWorkbookPath(
                roomName,
                request.VersionId
            );

            if (!System.IO.File.Exists(versionPath))
            {
                return NotFound(
                    "The requested version does not exist."
                );
            }

            SemaphoreSlim versionLock = GetVersionLock(roomName);
            await versionLock.WaitAsync();

            try
            {
                string roomDirectory =
                    GetRoomVersionDirectory(roomName);
                Directory.CreateDirectory(roomDirectory);

                string currentWorkbookPath = Path.Combine(
                    roomDirectory,
                    CurrentWorkbookName
                );

                System.IO.File.Copy(
                    versionPath,
                    currentWorkbookPath,
                    true
                );

                await actionService.ClearRecordsAsync(
                    roomName,
                    false
                );


                RestoreRevisionInfo restoreInfo =
                    RoomRestoreRevisions.AddOrUpdate(
                        roomName,
                        _ => new RestoreRevisionInfo
                        {
                            Revision = 1L,
                            RestoredBy = request.RestoredBy
                        },
                        (_, currentInfo) => new RestoreRevisionInfo
                        {
                            Revision = currentInfo.Revision + 1L,
                            RestoredBy = request.RestoredBy
                        }
                    );


                string payload = JsonConvert.SerializeObject(
                    new
                    {
                        roomName,
                        versionId = request.VersionId,
                        restoreRevision = restoreInfo.Revision,
                        restoredBy = restoreInfo.RestoredBy
                    },
                    ControllerJsonSettings
                );

                await transport.SendToGroupAsync(
                    roomName,
                    "versionRestored",
                    payload
                );

                return Ok();
            }
            finally
            {
                versionLock.Release();
            }
        }

        /// <summary>
        /// Downloads a specific version of the workbook as an XLSX file.
        /// </summary>
        /// <param name="request">The version request containing room name and version ID.</param>
        /// <returns>The workbook file as an attachment.</returns>
        [HttpPost]
        [Route("DownloadVersion")]
        [EnableCors("AllowAllOrigins")]
        public async Task<ActionResult> DownloadVersion(
            [FromBody] SpreadsheetVersionRequest request)
        {
            if (request == null ||
                string.IsNullOrWhiteSpace(request.RoomName) ||
                string.IsNullOrWhiteSpace(request.VersionId))
            {
                return BadRequest(
                    "Room name and version ID are required."
                );
            }

            string roomName = request.RoomName.Trim();
            string versionPath = GetVersionWorkbookPath(
                roomName,
                request.VersionId
            );

            if (!System.IO.File.Exists(versionPath))
            {
                return NotFound(
                    "The requested version does not exist."
                );
            }

            try
            {
                byte[] fileBytes = await System.IO.File.ReadAllBytesAsync(
                    versionPath
                );

                // Get version metadata for filename generation
                SpreadsheetVersionInfo versionInfo =
                    await GetVersionInfoAsync(
                        roomName,
                        request.VersionId
                    );

                string fileName = GenerateDownloadFileName(
                    versionInfo,
                    request.VersionId
                );

                return File(
                    fileBytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    fileName
                );
            }
            catch (Exception exception)
            {
                Console.WriteLine(
                    "Version download failed: " +
                    exception
                );
                return StatusCode(
                    500,
                    "Unable to download version."
                );
            }
        }

        /// <summary>
        /// Generates a meaningful filename for a downloaded version.
        /// </summary>
        /// <param name="versionInfo">The version metadata.</param>
        /// <param name="versionId">The version ID.</param>
        /// <returns>A formatted filename.</returns>
        private string GenerateDownloadFileName(
            SpreadsheetVersionInfo versionInfo,
            string versionId)
        {
            if (versionInfo == null)
            {
                return string.Format(
                    "Workbook_v{0}_{1:yyyy-MM-dd_HH-mm-ss}.xlsx",
                    versionId.Substring(0, Math.Min(8, versionId.Length)),
                    DateTime.UtcNow
                );
            }

            string baseFileName = string.IsNullOrWhiteSpace(
                versionInfo.FileName
            )
                ? "Workbook"
                : System.IO.Path.GetFileNameWithoutExtension(
                    versionInfo.FileName
                );

            return string.Format(
                "{0}_v{1}_{2:yyyy-MM-dd_HH-mm-ss}.xlsx",
                SanitizeFileName(baseFileName),
                versionInfo.CollaborationVersion,
                versionInfo.CreatedAtUtc
            );
        }

        /// <summary>
        /// Sanitizes a filename by removing invalid characters.
        /// </summary>
        /// <param name="fileName">The filename to sanitize.</param>
        /// <returns>A sanitized filename.</returns>
        private string SanitizeFileName(string fileName)
        {
            if (string.IsNullOrWhiteSpace(fileName))
            {
                return "Workbook";
            }

            char[] invalidCharacters =
                System.IO.Path.GetInvalidFileNameChars();

            return new string(
                fileName
                    .Where(character =>
                        !invalidCharacters.Contains(character)
                    )
                    .ToArray()
            );
        }

        /// <summary>
        /// Creates an immutable workbook version for a server-assigned action version.
        /// </summary>
        /// <param name="roomName">The collaboration room name.</param>
        /// <param name="action">The server-processed Spreadsheet action.</param>
        private async Task CreateAutomaticVersionAsync(
            string roomName,
            ActionInfo action,
            string currentUser)
        {
            SemaphoreSlim versionLock = GetVersionLock(roomName);
            await versionLock.WaitAsync();

            try
            {
                SpreadsheetVersionHistory history =
                    await ReadVersionHistoryAsync(roomName);

                if (history.Versions.Any(
                    version =>
                        version.CollaborationVersion == action.Version
                ))
                {
                    return;
                }

                MaterializedWorkbook materializedWorkbook =
                    await MaterializeRoomWorkbookAsync(
                        roomName,
                        action.Version
                    );

                if (materializedWorkbook == null)
                {
                    return;
                }

                string versionId = Guid.NewGuid().ToString("N");
                string roomDirectory =
                    GetRoomVersionDirectory(roomName);
                Directory.CreateDirectory(roomDirectory);

                string versionPath = Path.Combine(
                    roomDirectory,
                    versionId + ".xlsx"
                );

                await System.IO.File.WriteAllBytesAsync(
                    versionPath,
                    materializedWorkbook.WorkbookData
                );

                SpreadsheetVersionInfo versionInfo =
                    new SpreadsheetVersionInfo
                    {
                        VersionId = versionId,
                        FileName = DefaultWorkbookName,
                        ModifiedBy = string.IsNullOrWhiteSpace(currentUser)
                            ? "Guest User"
                            : currentUser,
                        CreatedAtUtc = DateTime.UtcNow,
                        CollaborationVersion =
                            materializedWorkbook.Version,
                        Action = GetActionText(
                            action,
                            "action",
                            "requestType"
                        ) ?? "Workbook changed"
                    };

                history.Versions.Add(versionInfo);
                await WriteVersionHistoryAsync(
                    roomName,
                    history
                );

                string versionPayload = JsonConvert.SerializeObject(
                    versionInfo,
                    ControllerJsonSettings
                );

                await transport.SendToGroupAsync(
                    roomName,
                    "versionSaved",
                    versionPayload
                );
            }
            finally
            {
                versionLock.Release();
            }
        }

        /// <summary>
        /// Retrieves a text value from the action payload without depending on
        /// a package-version-specific user property.
        /// </summary>
        /// <param name="action">The Spreadsheet action.</param>
        /// <param name="propertyNames">The property names to locate.</param>
        /// <returns>The first non-empty matching value.</returns>
        private static string GetActionText(
        ActionInfo action,
        params string[] propertyNames)
        {
            Newtonsoft.Json.Linq.JObject root =
                Newtonsoft.Json.Linq.JObject.FromObject(action);
            HashSet<string> names = new HashSet<string>(
                propertyNames,
                StringComparer.OrdinalIgnoreCase
            );

            Newtonsoft.Json.Linq.JProperty property =
                root
                    .Descendants()
                    .OfType<Newtonsoft.Json.Linq.JProperty>()
                    .FirstOrDefault(item =>
                        names.Contains(item.Name) &&
                        item.Value.Type ==
                            Newtonsoft.Json.Linq.JTokenType.String &&
                        !string.IsNullOrWhiteSpace(
                            item.Value.ToString()
                        )
                    );

            return property?.Value.ToString();
        }

        /// <summary>
        /// Returns the latest restore information for a collaboration room.
        /// </summary>
        /// <param name="roomName">The collaboration room name.</param>
        /// <returns>The current restore revision and restoring participant.</returns>
        [HttpGet]
        [Route("GetRestoreRevision/{roomName}")]
        [EnableCors("AllowAllOrigins")]
        public IActionResult GetRestoreRevision(string roomName)
        {
            RestoreRevisionInfo restoreInfo =
                string.IsNullOrWhiteSpace(roomName)
                    ? new RestoreRevisionInfo()
                    : RoomRestoreRevisions.GetOrAdd(
                        roomName,
                        _ => new RestoreRevisionInfo()
                    );

            string response = JsonConvert.SerializeObject(
                restoreInfo,
                ControllerJsonSettings
            );

            return Content(
                response,
                "application/json",
                Encoding.UTF8
            );
        }

        /// <summary>
        /// Creates an authoritative workbook snapshot for a collaboration room.
        /// </summary>
        /// <param name="roomName">The collaboration room name.</param>
        /// <param name="targetVersion">
        /// The last collaboration action version to include in the snapshot.
        /// When omitted, all currently pending actions are included.
        /// </param>
        /// <returns>The materialized workbook data and included version.</returns>
        private async Task<MaterializedWorkbook>
            MaterializeRoomWorkbookAsync(
                string roomName,
                int? targetVersion = null)
        {
            string workbookPath =
                GetRoomBaselineWorkbookPath(roomName);

            if (!System.IO.File.Exists(workbookPath))
            {
                return null;
            }

            List<CollaborationAction> collaborationActions =
                await actionService.GetPendingOperationsAsync(
                    roomName,
                    0,
                    -1
                );

            IEnumerable<ActionInfo> spreadsheetActionQuery =
                collaborationActions == null
                    ? Enumerable.Empty<ActionInfo>()
                    : collaborationActions
                        .Select(action =>
                            adapter.MapGenericToControlAction(
                                action
                            ) as ActionInfo
                        )
                        .Where(action => action != null);

            if (targetVersion.HasValue)
            {
                spreadsheetActionQuery =
                    spreadsheetActionQuery.Where(
                        action =>
                            action.Version <= targetVersion.Value
                    );
            }

            List<ActionInfo> spreadsheetActions =
                spreadsheetActionQuery
                    .OrderBy(action => action.Version)
                    .ToList();

            using (ExcelEngine excelEngine = new ExcelEngine())
            {
                IApplication application = excelEngine.Excel;
                IWorkbook workbook =
                    application.Workbooks.Open(workbookPath);

                try
                {
                    if (spreadsheetActions.Count > 0)
                    {
                        CollaborativeEditingHandler handler =
                            new CollaborativeEditingHandler(workbook);

                        foreach (ActionInfo action in spreadsheetActions)
                        {
                            handler.UpdateAction(action);
                        }
                    }

                    using (MemoryStream workbookStream =
                        new MemoryStream())
                    {
                        workbook.SaveAs(workbookStream);

                        return new MaterializedWorkbook
                        {
                            WorkbookData = workbookStream.ToArray(),
                            Version = spreadsheetActions.Count == 0
                                ? 0
                                : spreadsheetActions.Max(
                                    action => action.Version
                                )
                        };
                    }
                }
                finally
                {
                    workbook.Close();
                }
            }
        }

        private string ConvertWorkbookToJson(
            byte[] workbookData,
            string fileName)
        {
            using (MemoryStream workbookStream =
                new MemoryStream(workbookData))
            {
                string uploadFileName =
                    fileName.EndsWith(
                        ".xlsx",
                        StringComparison.OrdinalIgnoreCase
                    )
                        ? fileName
                        : fileName + ".xlsx";
                IFormFile formFile = new FormFile(
                    workbookStream,
                    0,
                    workbookStream.Length,
                    uploadFileName,
                    uploadFileName
                );
                OpenRequest openRequest = new OpenRequest
                {
                    File = formFile
                };

                return Workbook.Open(openRequest);
            }
        }

        [HttpPost]
        [Route("RegisterActionUser")]
        [EnableCors("AllowAllOrigins")]
        public ActionResult RegisterActionUser(
            [FromBody] RegisterActionUserRequest request)
        {
            if (request == null ||
                string.IsNullOrWhiteSpace(request.RoomName) ||
                string.IsNullOrWhiteSpace(request.CurrentUser))
            {
                return BadRequest();
            }

            RoomActionUsers.AddOrUpdate(
                request.RoomName,
                request.CurrentUser,
                (_, _) => request.CurrentUser
            );

            return Ok();
        }

        private string GetRoomBaselineWorkbookPath(string roomName)
        {
            string currentWorkbookPath = Path.Combine(
                GetRoomVersionDirectory(roomName),
                CurrentWorkbookName
            );

            if (System.IO.File.Exists(currentWorkbookPath))
            {
                return currentWorkbookPath;
            }

            return Path.Combine(
                hostingEnvironment.WebRootPath,
                "Files",
                DefaultWorkbookName
            );
        }

        private string GetRoomVersionDirectory(string roomName)
        {
            return Path.Combine(
                hostingEnvironment.ContentRootPath,
                "VersionData",
                SanitizePathSegment(roomName)
            );
        }

        private string GetVersionWorkbookPath(
            string roomName,
            string versionId)
        {
            return Path.Combine(
                GetRoomVersionDirectory(roomName),
                SanitizePathSegment(versionId) + ".xlsx"
            );
        }

        private async Task<SpreadsheetVersionHistory>
            ReadVersionHistoryAsync(string roomName)
        {
            string metadataPath = Path.Combine(
                GetRoomVersionDirectory(roomName),
                VersionMetadataFileName
            );

            if (!System.IO.File.Exists(metadataPath))
            {
                return new SpreadsheetVersionHistory();
            }

            string json = await System.IO.File.ReadAllTextAsync(
                metadataPath,
                Encoding.UTF8
            );

            if (string.IsNullOrWhiteSpace(json))
            {
                return new SpreadsheetVersionHistory();
            }

            return JsonConvert.DeserializeObject<
                SpreadsheetVersionHistory>(json) ??
                new SpreadsheetVersionHistory();
        }

        private async Task WriteVersionHistoryAsync(
            string roomName,
            SpreadsheetVersionHistory history)
        {
            string roomDirectory =
                GetRoomVersionDirectory(roomName);
            Directory.CreateDirectory(roomDirectory);

            string metadataPath = Path.Combine(
                roomDirectory,
                VersionMetadataFileName
            );
            string temporaryPath = metadataPath + ".tmp";
            string json = JsonConvert.SerializeObject(
                history,
                Formatting.Indented,
                ControllerJsonSettings
            );

            await System.IO.File.WriteAllTextAsync(
                temporaryPath,
                json,
                Encoding.UTF8
            );

            if (System.IO.File.Exists(metadataPath))
            {
                System.IO.File.Delete(metadataPath);
            }

            System.IO.File.Move(
                temporaryPath,
                metadataPath
            );
        }

        private async Task<SpreadsheetVersionInfo>
            GetVersionInfoAsync(
                string roomName,
                string versionId)
        {
            SpreadsheetVersionHistory history =
                await ReadVersionHistoryAsync(roomName);

            return history.Versions.FirstOrDefault(
                version => string.Equals(
                    version.VersionId,
                    versionId,
                    StringComparison.Ordinal
                )
            );
        }

        private static SemaphoreSlim GetVersionLock(
            string roomName)
        {
            return VersionLocks.GetOrAdd(
                roomName,
                _ => new SemaphoreSlim(1, 1)
            );
        }

        private static string SanitizePathSegment(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                return "default";
            }

            char[] invalidCharacters =
                Path.GetInvalidFileNameChars();
            string sanitizedValue = new string(
                value
                    .Where(character =>
                        !invalidCharacters.Contains(character) &&
                        character != Path.DirectorySeparatorChar &&
                        character != Path.AltDirectorySeparatorChar
                    )
                    .ToArray()
            );

            return string.IsNullOrWhiteSpace(sanitizedValue)
                ? "default"
                : sanitizedValue;
        }

        public class RemoveSelectionRequest
        {
            public string RoomName { get; set; }

            public string ConnectionId { get; set; }
        }

        public class DocumentContent
        {
            public int version { get; set; }

            public string sfdt { get; set; }
        }

        public class FileInfo
        {
            public string fileName { get; set; }

            public string roomName { get; set; }
        }

        private class MaterializedWorkbook
        {
            public byte[] WorkbookData { get; set; }

            public int Version { get; set; }
        }
    }
}
