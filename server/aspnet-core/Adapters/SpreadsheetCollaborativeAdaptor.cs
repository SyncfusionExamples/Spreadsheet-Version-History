using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Newtonsoft.Json;
using Newtonsoft.Json.Serialization;
using Syncfusion.Collaboration.Core.Interfaces;
using Syncfusion.Collaboration.Core.Models;
using Syncfusion.Collaboration.Core.Services;
using Syncfusion.EJ2.Spreadsheet;

namespace EJ2SpreadsheetServer.Adapters
{
    public class SpreadsheetCollaborativeAdaptor :
        ICollaborationAdapter
    {
        private static readonly JsonSerializerSettings
            OperationSettings = new JsonSerializerSettings
            {
                NullValueHandling =
                    NullValueHandling.Ignore,
                ContractResolver =
                    new DefaultContractResolver
                    {
                        NamingStrategy =
                            new CamelCaseNamingStrategy()
                    }
            };

        private readonly IServiceScopeFactory
            serviceScopeFactory;

        private readonly IBackgroundTaskQueue
            saveTaskQueue;

        public SpreadsheetCollaborativeAdaptor(
            IBackgroundTaskQueue saveTaskQueue,
            IServiceScopeFactory serviceScopeFactory)
        {
            this.saveTaskQueue = saveTaskQueue;
            this.serviceScopeFactory =
                serviceScopeFactory;
        }

        public CollaborationAction
            MapControlToGenericAction(
                object controlAction)
        {
            ActionInfo action =
                (ActionInfo)controlAction;

            return new CollaborationAction
            {
                RoomName = action.RoomName,
                ConnectionId = action.ConnectionId,
                CurrentUser = action.CurrentUser,
                Version = action.Version,
                ClientVersion = action.ClientVersion,
                IsTransformed = action.IsTransformed,
                Data = JsonConvert.SerializeObject(
                    action.Operations,
                    OperationSettings
                )
            };
        }

        public object MapGenericToControlAction(
            CollaborationAction action)
        {
            return new ActionInfo
            {
                RoomName = action.RoomName,
                ConnectionId = action.ConnectionId,
                CurrentUser = action.CurrentUser,
                Version = action.Version,
                ClientVersion = action.ClientVersion,
                IsTransformed = action.IsTransformed,
                Operations =
                    JsonConvert.DeserializeObject<
                        List<SpreadsheetOperation>>(
                            action.Data,
                            OperationSettings
                        )
            };
        }

        public void TransformOperations(
            List<CollaborationAction> actions)
        {
            if (actions == null || actions.Count < 2)
            {
                return;
            }

            List<ActionInfo> spreadsheetActions =
                actions
                    .Select(action =>
                        MapGenericToControlAction(
                            action
                        ) as ActionInfo
                    )
                    .Where(action => action != null)
                    .ToList();

            if (spreadsheetActions.Count < 2)
            {
                return;
            }

            bool transformed =
                CollaborativeEditingHandler
                    .TransformOperations(
                        spreadsheetActions
                    );

            if (!transformed)
            {
                return;
            }

            ActionInfo transformedTarget =
                spreadsheetActions[
                    spreadsheetActions.Count - 1
                ];

            CollaborationAction targetAction =
                actions[actions.Count - 1];

            targetAction.Data =
                JsonConvert.SerializeObject(
                    transformedTarget.Operations,
                    OperationSettings
                );

            targetAction.IsTransformed =
                transformedTarget.IsTransformed;
        }

        public async Task SaveOperationsAsync(
            List<CollaborationAction> actions,
            string roomName,
            bool partialSave)
        {
            if (actions == null ||
                actions.Count == 0 ||
                string.IsNullOrWhiteSpace(roomName))
            {
                return;
            }

            SaveRequest saveRequest = new SaveRequest
            {
                Actions = actions,
                PartialSave = partialSave,
                RoomName = roomName
            };

            await saveTaskQueue
                .QueueBackgroundWorkItemAsync(
                    saveRequest
                );
        }

        public async Task ProcessSaveRequestAsync(
            SaveRequest request,
            CancellationToken cancellationToken)
        {
            if (request == null ||
                string.IsNullOrWhiteSpace(
                    request.RoomName
                ))
            {
                return;
            }

            cancellationToken
                .ThrowIfCancellationRequested();

            using (IServiceScope serviceScope =
                serviceScopeFactory.CreateScope())
            {
                IActionService actionService =
                    serviceScope.ServiceProvider
                        .GetRequiredService<
                            IActionService>();

                await actionService.ClearRecordsAsync(
                    request.RoomName,
                    request.PartialSave
                );
            }
        }
    }
}
