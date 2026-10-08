<script setup lang="ts">
import {
    onBeforeUnmount,
    onMounted,
    provide,
    ref
} from 'vue';
import { Button } from '@syncfusion/ej2-buttons';
import { Tooltip } from '@syncfusion/ej2-popups';
import {
    SpreadsheetComponent as EjsSpreadsheet
} from '@syncfusion/ej2-vue-spreadsheet';
import {
    CollaborativeEditingHandler,
    type Spreadsheet
} from '@syncfusion/ej2-spreadsheet';
import { CollaborationClient } from '@syncfusion/ej2-collaborator';
import { SpreadsheetEditorAdapter } from './SpreadsheetEditorAdapter';
import {
    DialogComponent as EjsDialog
} from '@syncfusion/ej2-vue-popups';

/** Represents the metadata displayed for a saved workbook version. */
interface SpreadsheetVersionInfo {
    versionId: string;
    fileName: string;
    modifiedBy: string;
    createdAtUtc: string;
    collaborationVersion: number;
    action: string;
}

/** Represents the workbook content returned for a selected version. */
interface VersionWorkbookResponse {
    sfdt: string;
    version: number;
}

interface RestoreRevisionInfo {
    revision: number;
    restoredBy: string;
}

const serviceUrl: string = 'https://localhost:7002/';

const userNames: string[] = [
    'James Carter', 'Olivia Bennett', 'William Parker', 'Emma Collins',
    'Henry Mitchell', 'Amelia Foster', 'Benjamin Turner', 'Charlotte Morgan',
    'Lucas Anderson', 'Sophia Reynolds', 'Alexander Brooks', 'Isabella Hayes',
    'Daniel Cooper', 'Mia Richardson', 'Matthew Hughes', 'Evelyn Ward',
    'Samuel Peterson', 'Harper Jenkins', 'Joseph Sanders', 'Camila Bryant',
    'David Russell', 'Luna Griffin', 'Michael Perry', 'Sofia Coleman',
    'Ethan Powell', 'Avery Patterson', 'John Sullivan', 'Elizabeth Murphy',
    'Jack Hamilton', 'Eleanor Wallace', 'Owen Simmons', 'Abigail Butler',
    'Luke Henderson', 'Ella Fisher', 'Thomas Graham', 'Scarlett Woods',
    'George Marshall', 'Grace Spencer', 'Oliver Harrison', 'Chloe Matthews',
    'Leo Davidson', 'Victoria Palmer', 'Arthur Stevens', 'Lily Robertson',
    'Edward Kennedy', 'Hannah Thompson', 'Harry Phillips', 'Zoe Campbell',
    'Charles Edwards', 'Lucy Walker'
];

// Injects the collaborative editing service into the Spreadsheet.
provide('spreadsheet', [CollaborativeEditingHandler]);

const restoreDialogVisible = ref<boolean>(false);
const remoteRestoreDialogVisible = ref<boolean>(false);
const remoteRestoredBy = ref<string>('Another participant');

const spreadsheetRef = ref<InstanceType<typeof EjsSpreadsheet> | null>(null);
const shareButtonRef = ref<HTMLButtonElement | null>(null);
const versionHistoryVisible = ref<boolean>(false);
const versionHistoryLoading = ref<boolean>(false);
const versionPreviewLoading = ref<boolean>(false);
const versionHistory = ref<SpreadsheetVersionInfo[]>([]);
const selectedVersionId = ref<string>('');
const selectedVersion = ref<SpreadsheetVersionInfo | null>(null);
const isVersionHistoryMode = ref<boolean>(false);
const isViewingVersion = ref<boolean>(false);
const restoringVersion = ref<boolean>(false);
const downloadingVersion = ref<boolean>(false);
const currentUser: string =
    userNames[Math.floor(Math.random() * userNames.length)] ?? 'John Sullivan';

let adapter: SpreadsheetEditorAdapter | null = null;
let collaborationClient: CollaborationClient | null = null;
let shareButton: Button | null = null;
let copyButton: Button | null = null;
let shareTooltip: Tooltip | null = null;
let tooltipContent: HTMLElement | null = null;
let collaborationUrlInput: HTMLInputElement | null = null;
let copyButtonElement: HTMLButtonElement | null = null;
let copyResetTimer: number | null = null;
let versionHistoryRefreshTimer: number | null = null;
let initialized: boolean = false;
let suppressLocalActions: boolean = false;

let restoreRevisionTimer: number | null = null;
let lastRestoreRevision: number | null = null;
let restoreReloadInProgress: boolean = false;

/** Returns the collaboration room name from the URL or creates a new room name. */
function getRoomName(): string {
    const currentUrl: URL = new URL(window.location.href);
    let roomName: string = (currentUrl.searchParams.get('id') || '').trim();

    if (!roomName) {
        roomName = Math.random().toString(32).slice(2);
        currentUrl.searchParams.set('id', roomName);
        window.history.replaceState(
            window.history.state,
            '',
            currentUrl.pathname + currentUrl.search + currentUrl.hash
        );
    }

    return roomName;
}

/** Opens the restore confirmation dialog. */
function showRestoreConfirmation(): void {
    if (!selectedVersionId.value ||
        !selectedVersion.value ||
        restoringVersion.value) {
        return;
    }

    restoreDialogVisible.value = true;
}

/** Restores the selected version after confirmation. */
async function confirmRestore(): Promise<void> {
    restoreDialogVisible.value = false;
    await restoreSelectedVersion();
}

/** Closes the restore confirmation dialog. */
function cancelRestore(): void {
    restoreDialogVisible.value = false;
}

/** Returns the current Spreadsheet instance. */
function getSpreadsheet(): Spreadsheet | null {
    return spreadsheetRef.value?.ej2Instances as Spreadsheet | null;
}

/** Resets the copy button text when the Share tooltip is closed. */
function resetCopyButton(): void {
    if (copyButton) {
        copyButton.content = 'Copy URL';
        copyButton.dataBind();
    }
}

/** Closes the Share tooltip and clears the copy-state timer. */
function closeShareTooltip(): void {
    shareTooltip?.close();
    resetCopyButton();

    if (copyResetTimer !== null) {
        window.clearTimeout(copyResetTimer);
        copyResetTimer = null;
    }
}

/** Opens the collaboration Share tooltip. */
function openShareTooltip(): void {
    if (!shareButtonRef.value || !shareTooltip) {
        return;
    }

    resetCopyButton();

    if (collaborationUrlInput) {
        collaborationUrlInput.value = window.location.href;
    }

    shareTooltip.open(shareButtonRef.value);
}

/** Copies the collaboration URL and displays the copied state temporarily. */
async function copyUrl(): Promise<void> {
    try {
        await navigator.clipboard.writeText(window.location.href);

        if (copyButton) {
            copyButton.content = 'Copied';
            copyButton.dataBind();
        }

        if (copyResetTimer !== null) {
            window.clearTimeout(copyResetTimer);
        }

        copyResetTimer = window.setTimeout(closeShareTooltip, 1500);
    } catch (error) {
        console.error('[Collaborative Editing] Failed to copy the URL.', error);
    }
}

/** Creates the content displayed in the Share tooltip. */
function createShareTooltipContent(): HTMLElement {
    const content: HTMLDivElement = document.createElement('div');
    const label: HTMLLabelElement = document.createElement('label');
    const row: HTMLDivElement = document.createElement('div');
    const input: HTMLInputElement = document.createElement('input');
    const buttonElement: HTMLButtonElement = document.createElement('button');

    content.className = 'share-tooltip-content';
    label.className = 'share-url-label';
    label.htmlFor = 'collaboration-url';
    label.textContent = 'Collaboration URL';
    row.className = 'share-url-row';
    input.id = 'collaboration-url';
    input.className = 'e-input share-url-input';
    input.type = 'text';
    input.value = window.location.href;
    input.readOnly = true;
    input.setAttribute('aria-label', 'Collaboration URL');
    collaborationUrlInput = input;
    buttonElement.type = 'button';
    row.append(input, buttonElement);
    content.append(label, row);

    copyButton = new Button({
        content: 'Copy URL',
        cssClass: 'e-primary copy-url-button'
    });
    copyButton.appendTo(buttonElement);
    buttonElement.addEventListener('click', copyUrl);
    copyButtonElement = buttonElement;

    return content;
}

/** Closes the Share tooltip when a pointer action occurs outside it. */
function closeTooltipOnOutsideClick(event: MouseEvent): void {
    const target: Node = event.target as Node;
    const tooltipElement: Element | null = document.querySelector(
        '.collaboration-share-tooltip'
    );

    if (shareButtonRef.value?.contains(target) ||
        tooltipElement?.contains(target)) {
        return;
    }

    closeShareTooltip();
}

/** Closes the Share tooltip when the page is scrolled. */
function closeTooltipOnScroll(event: Event): void {
    const target: EventTarget | null = event.target;

    if (target instanceof Element && target.closest('.e-spreadsheet')) {
        return;
    }

    closeShareTooltip();
}

/** Starts periodic synchronization of the visible Version History list. */
function startVersionHistoryRefresh(): void {
    stopVersionHistoryRefresh();

    versionHistoryRefreshTimer = window.setInterval(() => {
        if (versionHistoryVisible.value &&
            !versionHistoryLoading.value &&
            !versionPreviewLoading.value) {
            void loadVersionHistory();
        }
    }, 2000);
}

/** Stops periodic Version History synchronization. */
function stopVersionHistoryRefresh(): void {
    if (versionHistoryRefreshTimer !== null) {
        window.clearInterval(versionHistoryRefreshTimer);
        versionHistoryRefreshTimer = null;
    }
}

/** Starts monitoring workbook restores performed by other participants. */
function startRestoreRevisionMonitor(): void {
    stopRestoreRevisionMonitor();

    restoreRevisionTimer = window.setInterval(() => {
        void checkRestoreRevision();
    }, 1500);
}

/** Stops monitoring workbook restores. */
function stopRestoreRevisionMonitor(): void {
    if (restoreRevisionTimer !== null) {
        window.clearInterval(restoreRevisionTimer);
        restoreRevisionTimer = null;
    }
}

/** Checks whether another participant restored the workbook. */
async function checkRestoreRevision(): Promise<void> {
    if (!adapter?.currentRoomName || restoreReloadInProgress) {
        return;
    }

    try {
        const response: Response = await fetch(
            serviceUrl +
                'api/CollaborativeEditing/GetRestoreRevision/' +
                encodeURIComponent(adapter.currentRoomName) +
                '?timestamp=' +
                Date.now(),
            {
                cache: 'no-store'
            }
        );

        if (!response.ok) {
            return;
        }

        const restoreInfo: RestoreRevisionInfo =
            await response.json() as RestoreRevisionInfo;

        if (lastRestoreRevision === null) {
            lastRestoreRevision = restoreInfo.revision;
            return;
        }

        if (restoreInfo.revision === lastRestoreRevision) {
            return;
        }

        lastRestoreRevision = restoreInfo.revision;
        restoreReloadInProgress = true;

        try {
            await reloadLatestWorkbook();

            if (restoreInfo.restoredBy !== currentUser) {
                remoteRestoredBy.value =
                    restoreInfo.restoredBy || 'Another participant';
                remoteRestoreDialogVisible.value = true;
            }
        } finally {
            restoreReloadInProgress = false;
        }
    } catch (error) {
        console.error(
            '[Version History] Failed to check the restore revision.',
            error
        );
    }
}

/** Synchronizes the restore revision in the initiating browser. */
async function synchronizeRestoreRevision(): Promise<void> {
    if (!adapter?.currentRoomName) {
        return;
    }

    try {
        const response: Response = await fetch(
            serviceUrl +
                'api/CollaborativeEditing/GetRestoreRevision/' +
                encodeURIComponent(adapter.currentRoomName) +
                '?timestamp=' +
                Date.now(),
            {
                cache: 'no-store'
            }
        );

        if (response.ok) {
            const restoreInfo: RestoreRevisionInfo =
                await response.json() as RestoreRevisionInfo;

            lastRestoreRevision = restoreInfo.revision;
        }
    } catch (error) {
        console.error(
            '[Version History] Failed to synchronize the restore revision.',
            error
        );
    }
}

/** Opens Version History from the remote restore notification. */
async function openHistoryFromRestoreNotice(): Promise<void> {
    remoteRestoreDialogVisible.value = false;
    await enterVersionHistoryMode();
}

/** Closes the remote restore notification. */
function closeRemoteRestoreNotice(): void {
    remoteRestoreDialogVisible.value = false;
}

/** Loads the synchronized workbook and joins the collaboration room. */
async function onCreated(): Promise<void> {
    const spreadsheet: Spreadsheet | null = getSpreadsheet();

    if (!spreadsheet || initialized) {
        return;
    }

    initialized = true;
    const roomName: string = getRoomName();
    const spreadsheetAdapter = new SpreadsheetEditorAdapter(
        spreadsheet,
        serviceUrl,
        currentUser,
        handleRemoteVersionSaved
    );

    try {
        await spreadsheetAdapter.loadFromServer('Sample', roomName);

        const client = new CollaborationClient(spreadsheetAdapter, {
            serviceUrl,
            connectionType: 'signalr',
            currentUser
        });

        adapter = spreadsheetAdapter;
        collaborationClient = client;
        await client.joinRoomAsync(roomName);
        await checkRestoreRevision();
        startRestoreRevisionMonitor();
        console.log('[Collaborative Editing] Joined room', roomName);
    } catch (error) {
        initialized = false;
        console.error('[Collaborative Editing] Failed to join the room.', error);
    }
}

/** Sends a completed local Spreadsheet action when live editing is active. */
function onActionComplete(args: unknown): void {
    if (suppressLocalActions || isVersionHistoryMode.value) {
        return;
    }

    adapter?.sendActionToServer(args);
}

/** Opens Version History and changes the Spreadsheet to read-only mode. */
async function enterVersionHistoryMode(): Promise<void> {
    const spreadsheet: Spreadsheet | null = getSpreadsheet();

    isVersionHistoryMode.value = true;
    versionHistoryVisible.value = true;
    adapter?.setVersionHistoryMode(true);

    if (spreadsheet) {
        spreadsheet.allowEditing = false;
        spreadsheet.showFormulaBar = false;
        spreadsheet.dataBind();
    }

    await loadVersionHistory();
    startVersionHistoryRefresh();
}

/** Opens the Version History panel. */
async function openVersionHistory(): Promise<void> {
    await enterVersionHistoryMode();
}

/** Closes Version History and returns to the latest collaborative workbook. */
async function closeVersionHistory(): Promise<void> {
    await backToDocument();
}

/** Retrieves the latest version metadata for the current room. */
async function loadVersionHistory(): Promise<void> {
    if (!adapter?.currentRoomName || versionHistoryLoading.value) {
        return;
    }

    versionHistoryLoading.value = true;

    try {
        const response: Response = await fetch(
            serviceUrl +
                'api/CollaborativeEditing/GetVersionHistory/' +
                encodeURIComponent(adapter.currentRoomName) +
                '?timestamp=' +
                Date.now(),
            {
                cache: 'no-store'
            }
        );

        if (!response.ok) {
            throw new Error(
                'GetVersionHistory failed: ' + response.status
            );
        }

        versionHistory.value =
            await response.json() as SpreadsheetVersionInfo[];
    } catch (error) {
        console.error('[Version History] Failed to load versions.', error);
    } finally {
        versionHistoryLoading.value = false;
    }
}

/** Loads a selected workbook version into the read-only Spreadsheet. */
async function openVersionPreview(
    version: SpreadsheetVersionInfo
): Promise<void> {
    const spreadsheet: Spreadsheet | null = getSpreadsheet();

    if (!adapter?.currentRoomName ||
        !spreadsheet ||
        versionPreviewLoading.value) {
        return;
    }

    versionPreviewLoading.value = true;
    suppressLocalActions = true;

    try {
        const response: Response = await fetch(
            serviceUrl + 'api/CollaborativeEditing/GetVersionWorkbook',
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    roomName: adapter.currentRoomName,
                    versionId: version.versionId
                })
            }
        );

        if (!response.ok) {
            const errorMessage: string = response.status === 404
                ? 'The selected version is no longer available.'
                : 'Failed to load version with status ' +
                    response.status +
                    '.';

            throw new Error(errorMessage);
        }

        const data: VersionWorkbookResponse =
            await response.json() as VersionWorkbookResponse;

        if (!data.sfdt) {
            throw new Error('Received invalid workbook data.');
        }

        await spreadsheet.openFromJson({
            file: data.sfdt
        });

        selectedVersionId.value = version.versionId;
        selectedVersion.value = version;
        isViewingVersion.value = true;

        spreadsheet.allowEditing = false;
        spreadsheet.showFormulaBar = false;
        spreadsheet.dataBind();
    } catch (error) {
        selectedVersionId.value = '';
        selectedVersion.value = null;
        isViewingVersion.value = false;

        console.error(
            '[Version History] Failed to preview the version.',
            error
        );
    } finally {
        suppressLocalActions = false;
        versionPreviewLoading.value = false;
    }
}

/** Reloads the latest collaborative workbook and enables editing. */
async function backToDocument(): Promise<void> {
    stopVersionHistoryRefresh();

    if (!adapter?.currentRoomName) {
        return;
    }

    suppressLocalActions = true;

    adapter.setVersionHistoryMode(false);

    try {
        await adapter.loadFromServer('Sample', adapter.currentRoomName);
        const spreadsheet: Spreadsheet | null = getSpreadsheet();

        if (spreadsheet) {
            spreadsheet.allowEditing = true;
            spreadsheet.showFormulaBar = true;
            spreadsheet.dataBind();
        }

        isVersionHistoryMode.value = false;
        isViewingVersion.value = false;
        selectedVersionId.value = '';
        selectedVersion.value = null;
        versionHistoryVisible.value = false;
    } catch (error) {
        console.error('[Version History] Failed to return to the document.', error);
    } finally {
        suppressLocalActions = false;
    }
}

/** Restores the selected workbook version as the current room state. */
async function restoreSelectedVersion(): Promise<void> {
    if (!adapter?.currentRoomName ||
        !selectedVersionId.value ||
        !selectedVersion.value ||
        restoringVersion.value) {
        return;
    }

    restoringVersion.value = true;

    try {
        const response: Response = await fetch(
            serviceUrl + 'api/CollaborativeEditing/RestoreVersion',
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    roomName: adapter.currentRoomName,
                    versionId: selectedVersionId.value,
                    restoredBy: currentUser
                })
            }
        );

        if (!response.ok) {
            throw new Error(
                'RestoreVersion failed: ' + response.status
            );
        }

        await reloadLatestWorkbook();
        await synchronizeRestoreRevision();
    } catch (error) {
        console.error(
            '[Version History] Failed to restore the version.',
            error
        );
    } finally {
        restoringVersion.value = false;
    }
}


/** Downloads the selected version as an XLSX file. */
async function downloadSelectedVersion(): Promise<void> {
    if (!adapter?.currentRoomName ||
        !selectedVersionId.value ||
        !selectedVersion.value ||
        downloadingVersion.value) {
        return;
    }

    downloadingVersion.value = true;

    try {
        const response: Response = await fetch(
            serviceUrl + 'api/CollaborativeEditing/DownloadVersion',
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    roomName: adapter.currentRoomName,
                    versionId: selectedVersionId.value
                })
            }
        );

        if (!response.ok) {
            const errorMessage = response.status === 404
                ? 'The selected version is no longer available.'
                : `Download failed with status ${response.status}. Please try again.`;
            throw new Error(errorMessage);
        }

        const blob: Blob = await response.blob();

        if (blob.size === 0) {
            throw new Error('Downloaded file is empty. Please try again.');
        }

        const url: string = window.URL.createObjectURL(blob);
        const link: HTMLAnchorElement = document.createElement('a');
        link.href = url;
        link.download = `${selectedVersion.value.fileName.replace(/\.xlsx$/i, '')}_v${selectedVersion.value.collaborationVersion}.xlsx`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error('[Version History] Failed to download the version.', error);
    } finally {
        downloadingVersion.value = false;
    }
}

/** Refreshes the visible history after another participant saves a version. */
async function handleRemoteVersionSaved(): Promise<void> {
    if (versionHistoryVisible.value) {
        await loadVersionHistory();
    }
}

/** Reloads the latest room workbook after a version restore. */
async function reloadLatestWorkbook(): Promise<void> {
    stopVersionHistoryRefresh();

    if (!adapter?.currentRoomName) {
        return;
    }

    suppressLocalActions = true;

    adapter.setVersionHistoryMode(false);

    try {
        await adapter.loadFromServer('Sample', adapter.currentRoomName);
        const spreadsheet: Spreadsheet | null = getSpreadsheet();

        if (spreadsheet) {
            spreadsheet.allowEditing = true;
            spreadsheet.showFormulaBar = true;
            spreadsheet.dataBind();
        }

        isVersionHistoryMode.value = false;
        isViewingVersion.value = false;
        selectedVersionId.value = '';
        selectedVersion.value = null;
        versionHistoryVisible.value = false;
    } catch (error) {
        console.error('[Version History] Failed to load the restored version.', error);
    } finally {
        suppressLocalActions = false;
    }
}

/** Formats a stored UTC version timestamp for display. */
function formatVersionDate(value: string): string {
    if (!value) {
        return 'Unknown date';
    }

    const date: Date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return 'Unknown date';
    }

    return new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short'
    }).format(date);
}

/** Initializes the Share button and tooltip after the component is mounted. */
onMounted(() => {
    if (!shareButtonRef.value) {
        return;
    }

    shareButton = new Button({
        content: 'Share',
        cssClass: 'e-primary share-button'
    });
    shareButton.appendTo(shareButtonRef.value);
    tooltipContent = createShareTooltipContent();
    shareTooltip = new Tooltip({
        content: tooltipContent,
        opensOn: 'Custom',
        position: 'BottomRight',
        cssClass: 'collaboration-share-tooltip'
    });
    shareTooltip.appendTo(shareButtonRef.value);
    shareButtonRef.value.addEventListener('click', openShareTooltip);
    document.addEventListener('mousedown', closeTooltipOnOutsideClick);
    window.addEventListener('scroll', closeTooltipOnScroll, true);
});

/** Releases timers, event handlers, controls, and collaboration references. */
onBeforeUnmount(() => {
    stopRestoreRevisionMonitor();
    stopVersionHistoryRefresh();
    shareButtonRef.value?.removeEventListener('click', openShareTooltip);
    document.removeEventListener('mousedown', closeTooltipOnOutsideClick);
    window.removeEventListener('scroll', closeTooltipOnScroll, true);
    copyButtonElement?.removeEventListener('click', copyUrl);

    if (copyResetTimer !== null) {
        window.clearTimeout(copyResetTimer);
    }

    shareTooltip?.destroy();
    shareButton?.destroy();
    copyButton?.destroy();
    tooltipContent = null;
    collaborationUrlInput = null;
    copyButtonElement = null;
    collaborationClient = null;
    adapter = null;
    initialized = false;
    lastRestoreRevision = null;
    restoreReloadInProgress = false;
});
</script>

<template>
    <div class="collaborative-sample">
        <div class="collaboration-info-bar">
            <div class="collaboration-info-text">
                Copy and share this demo URL with others to collaborate in real time.
                The link contains a unique session ID that connects all participants
                to the same workbook.
            </div>
            <div class="collaboration-actions">
                <button
                    type="button"
                    class="e-btn"
                    :disabled="isVersionHistoryMode"
                    @click="openVersionHistory"
                >
                    Version History
                </button>
                <div class="share-tooltip-host">
                    <button
                        id="share-collaboration-url"
                        ref="shareButtonRef"
                        type="button"
                    ></button>
                </div>
            </div>
        </div>
        <div
            v-if="isVersionHistoryMode"
            class="version-preview-bar"
        >
            <button
                type="button"
                class="back-to-document-button"
                @click="backToDocument"
            >
                Back to document
            </button>
            <span class="version-preview-date">
                {{
                    selectedVersion
                        ? formatVersionDate(selectedVersion.createdAtUtc)
                        : 'Current version'
                }}
            </span>
            <div class="version-preview-actions">
                <button
                    v-if="isViewingVersion"
                    type="button"
                    class="e-btn"
                    :disabled="downloadingVersion"
                    @click="downloadSelectedVersion"
                    title="Download this version as an Excel file"
                >
                    {{ downloadingVersion ? 'Downloading...' : 'Download a copy' }}
                </button>
                <button
                    v-if="isViewingVersion"
                    type="button"
                    class="e-btn e-primary"
                    :disabled="restoringVersion"
                    @click="showRestoreConfirmation"
                >
                    {{ restoringVersion ? 'Restoring...' : 'Restore' }}
                </button>
            </div>
        </div>
        <div class="workspace-container">
            <div
                class="spreadsheet-container"
                :class="{ 'version-history-mode': isVersionHistoryMode }"
            >
                <!-- Enables collaborative editing and read-only Version History mode. -->
                <ejs-spreadsheet
                    ref="spreadsheetRef"
                    width="100%"
                    height="100%"
                    :enableCollaborativeEditing="true"
                    :allowEditing="!isVersionHistoryMode"
                    :created="onCreated"
                    :actionComplete="onActionComplete"
                />
                <div
                    v-if="versionPreviewLoading"
                    class="version-preview-loading"
                >
                    Loading version...
                </div>
            </div>
            <aside
                v-if="versionHistoryVisible"
                class="version-history-panel"
            >
                <div class="version-history-header">
                    <strong>Version History</strong>
                    <button
                        type="button"
                        class="version-history-close"
                        aria-label="Close version history"
                        @click="closeVersionHistory"
                    >
                        ×
                    </button>
                </div>
                <div
                    v-if="versionHistoryLoading"
                    class="version-history-empty"
                >
                    Loading versions...
                </div>
                <div
                    v-else-if="versionHistory.length === 0"
                    class="version-history-empty"
                >
                    No saved versions are available.
                </div>
                <template v-else>
                    <button
                        v-for="version in versionHistory"
                        :key="version.versionId"
                        type="button"
                        class="version-history-item"
                        :class="{
                            'version-history-item-selected':
                                selectedVersionId === version.versionId
                        }"
                        @click="openVersionPreview(version)"
                    >
                        <span class="version-history-date">
                            {{ formatVersionDate(version.createdAtUtc) }}
                        </span>
                        <span class="version-history-user">
                            {{ version.modifiedBy }} {{ version.action || 'modified' }}
                        </span>
                    </button>
                </template>
            </aside>
        </div>
        <ejs-dialog
            v-model:visible="restoreDialogVisible"
            width="520px"
            header="Proceed with Restore?"
            :isModal="true"
            :showCloseIcon="true"
            :closeOnEscape="true"
            cssClass="restore-version-dialog"
            @close="cancelRestore"
        >
            <div class="restore-dialog-content">
                <p class="restore-dialog-message">
                    Other people may currently be working in this workbook.
                    Restoring a previous version will refresh the workbook for everyone.
                </p>
                <div class="restore-dialog-actions">
                    <button
                        type="button"
                        class="e-btn"
                        @click="cancelRestore"
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        class="e-btn e-primary"
                        :disabled="restoringVersion"
                        @click="confirmRestore"
                    >
                        {{ restoringVersion ? 'Restoring...' : 'Restore' }}
                    </button>
                </div>
            </div>
        </ejs-dialog>
        <ejs-dialog
            v-model:visible="remoteRestoreDialogVisible"
            width="620px"
            header="Workbook restored to previous version"
            :isModal="true"
            :showCloseIcon="true"
            :closeOnEscape="true"
            cssClass="remote-restore-dialog"
            @close="closeRemoteRestoreNotice"
        >
            <div class="remote-restore-content">
                <div class="remote-restore-message">
                    {{ remoteRestoredBy }} restored this workbook to a previous
                    version. You can open Version History to view and compare
                    previous versions of the workbook.
                </div>
                <div class="remote-restore-actions">
                    <button
                        type="button"
                        class="e-btn e-primary"
                        @click="openHistoryFromRestoreNotice"
                    >
                        Open Version History
                    </button>
                    <button
                        type="button"
                        class="e-btn"
                        @click="closeRemoteRestoreNotice"
                    >
                        Close
                    </button>
                </div>
            </div>
        </ejs-dialog>
    </div>
</template>
