using System;
using System.Collections.Generic;

namespace EJ2SpreadsheetServer.Models
{
    public class CreateSpreadsheetVersionRequest
    {
        public string RoomName { get; set; }

        public string FileName { get; set; }

        public string ModifiedBy { get; set; }
    }

    public class SpreadsheetVersionRequest
    {
        public string RoomName { get; set; }

        public string VersionId { get; set; }
    }

    public class SpreadsheetVersionInfo
    {
        public string VersionId { get; set; }

        public string FileName { get; set; }

        public string ModifiedBy { get; set; }

        public DateTime CreatedAtUtc { get; set; }

        public int CollaborationVersion { get; set; }
    }

    public class SpreadsheetVersionHistory
    {
        public List<SpreadsheetVersionInfo> Versions { get; set; } =
            new List<SpreadsheetVersionInfo>();
    }
}
