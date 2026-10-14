using System;
using System.Collections.Generic;

namespace EJ2SpreadsheetServer.Models
{

    public class SpreadsheetVersionRequest
    {
        public string RoomName { get; set; }

        public string VersionId { get; set; }
        public string? RestoredBy { get; set; }
    }

    public class RestoreRevisionInfo
    {
        public long Revision { get; set; }

        public string RestoredBy { get; set; }
    }

    public class SpreadsheetVersionInfo
    {
        public string VersionId { get; set; }

        public string FileName { get; set; }

        public string ModifiedBy { get; set; }

        public DateTime CreatedAtUtc { get; set; }

        public int CollaborationVersion { get; set; }

        public string Action { get; set; }
    }

    public class SpreadsheetVersionHistory
    {
        public List<SpreadsheetVersionInfo> Versions { get; set; } =
            new List<SpreadsheetVersionInfo>();
    }

    public class RegisterActionUserRequest
    {
        public string RoomName { get; set; }

        public string CurrentUser { get; set; }
    }
}
