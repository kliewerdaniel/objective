// afterSign hook for electron-builder
// Notarizes the macOS app using Apple's notary service
//
// Required environment variables:
//   APPLE_ID - Apple ID email
//   APPLE_APP_SPECIFIC_PASSWORD - App-specific password
//   APPLE_TEAM_ID - Apple Developer Team ID

const { notarize } = require('@electron/notarize')

exports.default = async function notarizing(context) {
  const { electronPlatformName, appOutDir } = context

  if (electronPlatformName !== 'darwin') {
    console.log('Skipping notarization: not macOS')
    return
  }

  const appName = context.packager.appInfo.productFilename
  const appPath = `${appOutDir}/${appName}.app`

  console.log(`Notarizing ${appPath}...`)

  const appleId = process.env.APPLE_ID
  const appleIdPassword = process.env.APPLE_APP_SPECIFIC_PASSWORD
  const teamId = process.env.APPLE_TEAM_ID

  if (!appleId || !appleIdPassword || !teamId) {
    console.warn('Skipping notarization: missing APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD, or APPLE_TEAM_ID')
    return
  }

  await notarize({
    appPath,
    appleId,
    appleIdPassword,
    teamId,
  })

  console.log('Notarization complete')
}
