-- 게임 알림을 로블록스 채팅창에 시스템 메시지로 띄운다.

local StarterGui = game:GetService("StarterGui")
local TextChatService = game:GetService("TextChatService")

local COLORS = {
	info = "#E8E2D0",
	good = "#9FE0C4",
	bad = "#F19A8A",
	tribulation = "#F2B05E",
	world = "#F0D79A",
}

local Chat = {}

local channel: TextChannel? = nil

local function escape(text: string): string
	return (text:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"))
end

local function generalChannel(): TextChannel?
	if channel and channel.Parent then
		return channel
	end
	local channels = TextChatService:WaitForChild("TextChannels", 10)
	local general = channels and channels:WaitForChild("RBXGeneral", 10)
	if general and general:IsA("TextChannel") then
		channel = general
	end
	return channel
end

function Chat.system(text: string, kind: string?)
	local color = COLORS[kind or "info"] or COLORS.info
	task.spawn(function()
		if TextChatService.ChatVersion == Enum.ChatVersion.TextChatService then
			local general = generalChannel()
			if general then
				general:DisplaySystemMessage(string.format('<font color="%s">%s</font>', color, escape(text)))
				return
			end
		end
		-- 예전 채팅 시스템
		for _ = 1, 10 do
			local ok = pcall(function()
				StarterGui:SetCore("ChatMakeSystemMessage", { Text = text, Color = Color3.fromHex(color) })
			end)
			if ok then
				return
			end
			task.wait(1)
		end
	end)
end

return Chat
