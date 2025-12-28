// Add this function after showUserChats function in admin.js

/**
 * Show all files for a specific user
 * @param {number} userId - The user ID
 * @param {string} userEmail - The user's email address
 */
function showUserFiles(userId, userEmail) {
    console.log(`showUserFiles called with userId=${userId}, userEmail=${userEmail}`);

    // Filter files by user email
    const userFiles = filesData.filter(file => file.owner_email === userEmail);

    console.log(`Found ${userFiles.length} files for user`);

    // Simply scroll to files table and highlight user's files
    const searchInput = document.getElementById('searchFiles');
    if (searchInput) {
        searchInput.value = userEmail;
        searchInput.focus();
        filterFiles();

        // Scroll to files section
        const filesCard = document.querySelector('.table-card:nth-of-type(2)');
        if (filesCard) {
            filesCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        showToast(`Showing ${userFiles.length} files for ${userEmail}`);
    }
}
