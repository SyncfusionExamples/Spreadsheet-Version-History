import type {
    ICollaborationActionData,
    ICollaborationProvider
} from '@syncfusion/ej2-collaborator';
import type { Spreadsheet } from '@syncfusion/ej2-spreadsheet';

interface ImportFileResponse {
    sfdt: string;
    version: number;
}

/** Connects the Spreadsheet with the Collaboration Client and Server. */
export class SpreadsheetEditorAdapter implements ICollaborationProvider {
    public currentRoomName: string = '';

    /**
     * Initializes a new instance of the Spreadsheet collaboration adapter.
     *
     * @param spreadsheet - The Spreadsheet instance used for collaborative editing.
     * @param serviceUrl - The Collaboration Server URL.
     * @param currentUser - The display name of the current participant.
     * @param onVersionRestored - The callback invoked when a workbook version is restored.
     * @param onVersionSaved - The callback invoked when a workbook version is saved.
     */
    public constructor(
        private spreadsheet: Spreadsheet,
        private serviceUrl: string,
        private currentUser: string,
        private onVersionRestored: () => Promise<void>,
        private onVersionSaved: () => Promise<void>
    ) {
        this.serviceUrl = serviceUrl.endsWith('/')
            ? serviceUrl
            : serviceUrl + '/';
    }

    /**
     * Loads the latest synchronized workbook and initializes the collaboration room.
     *
     * @param fileName - The name of the workbook to load.
     * @param roomName - The unique collaboration room name.
     */
    public async loadFromServer(
        fileName: string,
        roomName: string
    ): Promise<void> {
        const response: Response = await fetch(
            this.serviceUrl + 'api/CollaborativeEditing/ImportFile',
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    fileName,
                    roomName
                })
            }
        );

        if (!response.ok) {
            throw new Error('Failed to load the workbook.');
        }

        const data: ImportFileResponse = JSON.parse(await response.text());
        this.currentRoomName = roomName;
        this.spreadsheet.collaborativeEditingModule.updateRoomInfo(
            roomName,
            data.version,
            this.serviceUrl + 'api/CollaborativeEditing/'
        );
        this.spreadsheet.collaborativeEditingModule.setLocalUser(
            this.currentUser
        );
        await this.spreadsheet.openFromJson({
            file: data.sfdt
        });
    }

    /**
     * Sends a completed local Spreadsheet action to the Collaboration Server.
     *
     * @param action - The completed Spreadsheet action.
     */
    public sendActionToServer(action: unknown): void {
        if (action) {
            this.spreadsheet.collaborativeEditingModule.sendActionToServer(
                action
            );
        }
    }

    /**
     * Applies an action received from another participant to the Spreadsheet.
     *
     * @param action - The collaborative action name.
     * @param data - The collaborative action data received from the server.
     */
    public applyRemoteAction(
        action: string,
        data: ICollaborationActionData
    ): void {
        if (action === 'versionRestored') {
            void this.onVersionRestored();
            return;
        }

        if (action === 'versionSaved') {
            void this.onVersionSaved();
            return;
        }

        if (!data) {
            return;
        }

        this.spreadsheet.collaborativeEditingModule.applyRemoteAction(
            action,
            data.payload
        );
    }
}
