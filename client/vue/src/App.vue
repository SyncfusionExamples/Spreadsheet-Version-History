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

/** Represents the metadata displayed for a saved workbook version. */
interface SpreadsheetVersionInfo {
    versionId: string;
    fileName: string;
    modifiedBy: string;
    createdAtUtc: string;
    collaborationVersion: number;
}

/** Represents the workbook content returned for a selected version. */
interface VersionWorkbookResponse {
    sfdt: string;
    version: number;
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
const savingVersion = ref<boolean>(false);
const restoringVersion = ref<boolean>(false);
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
        handleRemoteVersionRestore,
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

/** Saves the latest synchronized workbook state as a new version. */
async function saveVersion(): Promise<void> {
    if (!adapter?.currentRoomName ||
        savingVersion.value ||
        isVersionHistoryMode.value) {
        return;
    }

    savingVersion.value = true;

    try {
        const response: Response = await fetch(
            serviceUrl + 'api/CollaborativeEditing/SaveVersion',
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    roomName: adapter.currentRoomName,
                    fileName: 'Sample.xlsx',
                    modifiedBy: currentUser
                })
            }
        );

        if (!response.ok) {
            throw new Error('SaveVersion failed: ' + response.status);
        }

        await enterVersionHistoryMode();
    } catch (error) {
        console.error(
            '[Version History] Failed to save the version.',
            error
        );
    } finally {
        savingVersion.value = false;
    }
}

/** Opens Version History and changes the Spreadsheet to read-only mode. */
async function enterVersionHistoryMode(): Promise<void> {
    const spreadsheet: Spreadsheet | null = getSpreadsheet();

    isVersionHistoryMode.value = true;
    versionHistoryVisible.value = true;

    if (spreadsheet) {
        spreadsheet.allowEditing = false;
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
    selectedVersionId.value = version.versionId;
    selectedVersion.value = version;
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
            throw new Error(
                'GetVersionWorkbook failed: ' + response.status
            );
        }

        const data: VersionWorkbookResponse =
            await response.json() as VersionWorkbookResponse;

        await spreadsheet.openFromJson({
            file: data.sfdt
        });
        isViewingVersion.value = true;
        spreadsheet.allowEditing = false;
        spreadsheet.dataBind();
    } catch (error) {
        selectedVersionId.value = '';
        selectedVersion.value = null;
        console.error('[Version History] Failed to preview the version.', error);
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

    try {
        await adapter.loadFromServer('Sample', adapter.currentRoomName);
        const spreadsheet: Spreadsheet | null = getSpreadsheet();

        if (spreadsheet) {
            spreadsheet.allowEditing = true;
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
                    versionId: selectedVersionId.value
                })
            }
        );

        if (!response.ok) {
            throw new Error(
                'RestoreVersion failed: ' + response.status
            );
        }

        await reloadLatestWorkbook();
    } catch (error) {
        console.error('[Version History] Failed to restore the version.', error);
    } finally {
        restoringVersion.value = false;
    }
}

/** Reloads the workbook after another participant restores a version. */
async function handleRemoteVersionRestore(): Promise<void> {
    await reloadLatestWorkbook();
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

    try {
        await adapter.loadFromServer('Sample', adapter.currentRoomName);
        const spreadsheet: Spreadsheet | null = getSpreadsheet();

        if (spreadsheet) {
            spreadsheet.allowEditing = true;
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
                    class="e-btn e-primary"
                    :disabled="savingVersion || isVersionHistoryMode"
                    @click="saveVersion"
                >
                    {{ savingVersion ? 'Saving...' : 'Save Version' }}
                </button>
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
            <button
                v-if="isViewingVersion"
                type="button"
                class="e-btn e-primary"
                :disabled="restoringVersion"
                @click="restoreSelectedVersion"
            >
                {{ restoringVersion ? 'Restoring...' : 'Restore' }}
            </button>
            <span v-else></span>
        </div>
        <div class="workspace-container">
            <div class="spreadsheet-container">
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
                            {{ version.modifiedBy }} modified
                        </span>
                    </button>
                </template>
            </aside>
        </div>
    </div>
</template>
